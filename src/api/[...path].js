export default async function handler(req, res) {
  const targetHost = process.env.SOUNDVECTOR_API_BASE;

  const path = req.query.path;
  const pathStr = Array.isArray(path) ? path.join('/') : (path || '');
  const queryIdx = req.url.indexOf('?');
  const queryString = queryIdx !== -1 ? req.url.substring(queryIdx) : '';

  const targetUrl = `${targetHost.replace(/\/$/, '')}/api/${pathStr}${queryString}`;

  try {
    const options = {
      method: req.method,
      headers: {
        'content-type': req.headers['content-type'] || 'application/json',
      }
    };

    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) {
      options.body = typeof req.body === 'object' ? JSON.stringify(req.body) : req.body;
    }

    const response = await fetch(targetUrl, options);
    const data = await response.text();

    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', response.headers.get('content-type') || 'application/json');
    res.status(response.status).send(data);
  } catch (err) {
    res.status(500).json({ error: "Backend proxy error", details: err.message });
  }
}
