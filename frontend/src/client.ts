import { createClient } from "@supabase/supabase-js";
const url = import.meta.env["VITE_SUPABASE_URL"],
  key = import.meta.env["VITE_SUPABASE_ANON_KEY"];
export const db = url && key ? createClient(url, key) : null;
export async function rpc<T = unknown>(
  name: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  if (!db)
    throw Error(
      "Local Supabase needs setup. Run the start-local script in the project.",
    );
  const { data, error } = await db.rpc(name, args);
  if (error)
    throw Error(
      error.code === "23505"
        ? "That name is already in use. Choose another."
        : error.message,
    );
  return data as T;
}
export type Profile = {
  id: string;
  username: string;
  display_name: string;
  avatar_path: string | null;
};
export type Org = { id: string; name: string; owner_id: string };
export type Role = { id: string; name: string; builtin: boolean };
export type Person = {
  user_id: string;
  username: string;
  role_id: string;
  avatar_path: string | null;
};
export type Invite = {
  id: string;
  user_id: string;
  role_id: string;
  status: string;
  organization_name: string;
  org_id: string;
};
export type Source = { id: string; name: string; dialect: string };
export type Rule = { table: string; column: string; op: "eq"; value: string };
export type Policy = {
  database_id: string;
  role_id: string | null;
  user_id: string | null;
  mode: string;
  table_columns: Record<string, string[]>;
  row_rules: Rule[];
};
export async function rows<T>(
  table: string,
  filters: Record<string, string> = {},
): Promise<T[]> {
  if (!db) throw Error("Local Supabase is unavailable.");
  let q = db.from(table).select("*");
  for (const [k, v] of Object.entries(filters)) q = q.eq(k, v);
  const { data, error } = await q;
  if (error) throw Error(error.message);
  return (data || []) as T[];
}
export async function uploadAvatar(file: File, id: string) {
  if (!db) throw Error("Local Supabase is unavailable.");
  if (
    !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    file.size > 12 * 1024 * 1024
  )
    throw Error("Choose a JPG, PNG or WebP under 12 MB.");
  const image = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 320;
  const edge = Math.min(image.width, image.height);
  canvas
    .getContext("2d")!
    .drawImage(
      image,
      (image.width - edge) / 2,
      (image.height - edge) / 2,
      edge,
      edge,
      0,
      0,
      320,
      320,
    );
  image.close();
  const blob = await new Promise<Blob | null>((res) =>
    canvas.toBlob(res, "image/webp", 0.86),
  );
  if (!blob) throw Error("This browser could not convert the image.");
  const path = id + "/profile.webp";
  const { error } = await db.storage
    .from("avatars")
    .upload(path, blob, { upsert: true, contentType: "image/webp" });
  if (error) throw error;
  return path;
}
