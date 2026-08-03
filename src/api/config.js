export default function handler(req, res) {
  const apiBase = process.env.SOUNDVECTOR_API_BASE || process.env.HF_SPACE_URL || process.env.NEXT_PUBLIC_HF_SPACE_URL || "";
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(200).json({ api_base: apiBase });
}
