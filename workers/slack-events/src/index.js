/**
 * Cloudflare Worker: verify Slack Events API requests and dispatch GitHub Actions.
 */

function timingSafeEqual(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  let out = 0;
  for (let i = 0; i < a.length; i += 1) {
    out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return out === 0;
}

async function verifySlackRequest(request, signingSecret) {
  const timestamp = request.headers.get("x-slack-request-timestamp") || "";
  const signature = request.headers.get("x-slack-signature") || "";
  if (!timestamp || !signature) {
    throw new Error("Missing Slack signature headers.");
  }

  const skew = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(skew) || skew > 60 * 5) {
    throw new Error("Slack request timestamp is too old.");
  }

  const body = await request.text();
  const base = `v0:${timestamp}:${body}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(base));
  const hex = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  const expected = `v0=${hex}`;
  if (!timingSafeEqual(expected, signature)) {
    throw new Error("Invalid Slack signature.");
  }

  return { body, payload: JSON.parse(body) };
}

function shouldForwardEvent(event) {
  if (!event || typeof event !== "object") {
    return false;
  }
  if (event.bot_id) {
    return false;
  }
  if (["bot_message", "message_changed", "message_deleted"].includes(event.subtype)) {
    return false;
  }
  return ["reaction_added", "reaction_removed", "message"].includes(event.type);
}

function encodeEventB64(event) {
  const bytes = new TextEncoder().encode(JSON.stringify(event));
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

async function dispatchSlackApproveWorkflow(env, event, eventId) {
  const token = env.GITHUB_TOKEN;
  const repo = env.GITHUB_REPOSITORY;
  const ref = env.GITHUB_REF_NAME || "main";
  if (!token || !repo) {
    throw new Error("GITHUB_TOKEN and GITHUB_REPOSITORY must be configured on the Worker.");
  }

  const response = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/slack_approve.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "peachtree-slack-worker",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      ref,
      inputs: {
        event_b64: encodeEventB64(event),
        event_id: eventId || `${event.type}-${Date.now()}`,
      },
    }),
  });

  if (response.status !== 204) {
    const detail = await response.text();
    throw new Error(`GitHub dispatch failed: HTTP ${response.status} ${detail}`);
  }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "GET") {
      const url = new URL(request.url);
      if (url.pathname === "/health") {
        return Response.json({ status: "ok" });
      }
      return new Response("Peachtree Slack Events Worker", { status: 200 });
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/slack/events") {
      return new Response("Not Found", { status: 404 });
    }

    const signingSecret = env.SLACK_SIGNING_SECRET;
    if (!signingSecret) {
      return new Response("SLACK_SIGNING_SECRET is not configured.", { status: 500 });
    }

    let payload;
    try {
      ({ payload } = await verifySlackRequest(request, signingSecret));
    } catch (error) {
      return new Response(String(error.message || error), { status: 401 });
    }

    if (payload.type === "url_verification") {
      return Response.json({ challenge: payload.challenge });
    }

    if (payload.type === "event_callback") {
      const event = payload.event || {};
      if (shouldForwardEvent(event)) {
        ctx.waitUntil(
          dispatchSlackApproveWorkflow(env, event, payload.event_id || "").catch((error) => {
            console.error("dispatch failed", error);
          }),
        );
      }
      return Response.json({ ok: true });
    }

    return Response.json({ ok: true });
  },
};
