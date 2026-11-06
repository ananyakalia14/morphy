// Local-only, disposable test accounts. Run after start-local.ps1.
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
const base = process.env.VITE_SUPABASE_URL || "http://127.0.0.1:55421";
const key = process.env.VITE_SUPABASE_ANON_KEY;
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname) || !key)
  throw Error("Supply a LOCAL Supabase URL and its public key.");
const suffix = randomBytes(5).toString("hex");
async function request(
  path,
  { token = key, method = "GET", body, headers = {} } = {},
) {
  const r = await fetch(base + path, {
    method,
    headers: {
      apikey: key,
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const raw = await r.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    data = raw;
  }
  return { ok: r.ok, status: r.status, data };
}
function checked(r) {
  assert.ok(r.ok, JSON.stringify(r.data));
  return r.data;
}
async function user(tag) {
  const { access_token, user } = checked(
    await request("/auth/v1/signup", {
      method: "POST",
      body: {
        email: tag + suffix + "@example.test",
        password: randomBytes(24).toString("hex"),
      },
    }),
  );
  assert.ok(access_token, "Local test email confirmation must be disabled.");
  const call = (name, args) =>
    request("/rest/v1/rpc/" + name, {
      token: access_token,
      method: "POST",
      body: args,
    });
  return {
    id: user.id,
    token: access_token,
    call,
    read: (path) => request("/rest/v1/" + path, { token: access_token }),
  };
}
const [a, b] = await Promise.all([user("owner"), user("member")]);
const shared = "claim_" + suffix;
const race = await Promise.all(
  [a, b].map((p) =>
    p.call("claim_profile", { handle: shared, full_name: "Concurrent test" }),
  ),
);
assert.equal(race.filter((r) => r.ok).length, 1);
assert.equal(race.find((r) => !r.ok).data.code, "23505");
checked(
  await [a, b][race.findIndex((r) => !r.ok)].call("claim_profile", {
    handle: "other_" + suffix,
    full_name: "Second user",
  }),
);
const org = checked(
  await a.call("create_workspace", { title: "Alpha " + suffix }),
);
await b.call("create_workspace", { title: "Beta " + suffix }).then(checked);
assert.deepEqual(checked(await b.read("organizations?id=eq." + org)), []);
const roles = checked(await a.read("roles?org_id=eq." + org));
const viewer = roles.find((r) => r.name === "VIEWER").id;
const admin = roles.find((r) => r.name === "ADMIN").id;
const d = checked(
  await a.call("register_database", {
    o: org,
    title: "Warehouse",
    engine: "postgres",
  }),
);
checked(
  await a.call("save_permission", {
    o: org,
    d,
    r: viewer,
    person: null,
    level: "QUERY_ONLY",
    cols: { orders: ["region", "amount"] },
    rules: [{ table: "orders", column: "region", op: "eq", value: "APAC" }],
  }),
);
checked(await a.call("invite_person", { o: org, person: b.id, r: viewer }));
const inv = checked(await b.read("invitations?org_id=eq." + org))[0].id;
assert.equal((await a.call("accept_invitation", { inv })).ok, false);
checked(await b.call("accept_invitation", { inv }));
checked(await b.call("accept_invitation", { inv }));
assert.equal(
  (await b.call("set_member_role", { o: org, person: b.id, r: admin })).ok,
  false,
);
assert.equal(
  (await b.call("transfer_owner", { o: org, person: b.id })).ok,
  false,
);
checked(
  await a.call("save_permission", {
    o: org,
    d,
    r: null,
    person: b.id,
    level: "SCHEMA_EDIT",
    cols: { orders: ["region", "ssn"] },
    rules: [],
  }),
);
assert.deepEqual(checked(await b.call("effective_permission", { d })), {
  mode: "QUERY_ONLY",
  table_columns: { orders: ["region"] },
  row_rules: [{ table: "orders", column: "region", op: "eq", value: "APAC" }],
});
checked(await a.call("transfer_owner", { o: org, person: b.id }));
assert.equal(
  checked(await a.read("organizations?id=eq." + org))[0].owner_id,
  b.id,
);
if (!process.env.MORPHY_POLICY_FIXTURE) {
  const webp = Buffer.from(
    "UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA",
    "base64",
  );
  async function putAvatar(p) {
    return fetch(
      base + "/storage/v1/object/avatars/" + a.id + "/profile.webp",
      {
        method: "POST",
        headers: {
          apikey: key,
          Authorization: "Bearer " + p.token,
          "content-type": "image/webp",
          "x-upsert": "true",
        },
        body: webp,
      },
    );
  }
  assert.ok((await putAvatar(a)).ok);
  assert.ok(!(await putAvatar(b)).ok);
}
console.log(
  "PASS · simultaneous claims, two organizations, wrong recipient, role escalation, role/user intersections and ownership transfer" +
    (process.env.MORPHY_POLICY_FIXTURE
      ? " (standalone PostgREST)"
      : " and Storage overwrite isolation"),
);
