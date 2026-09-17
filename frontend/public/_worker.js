export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Proxy all REST API calls directly to the Vercel backend
    if (url.pathname.startsWith('/api/')) {
      const targetUrl = 'https://cuti-tools.vercel.app' + url.pathname + url.search;
      const proxyRequest = new Request(targetUrl, request);
      proxyRequest.headers.set('host', 'cuti-tools.vercel.app');
      return fetch(proxyRequest);
    }

    // Serve static assets with SPA fallback to /index.html
    let response = await env.ASSETS.fetch(request);
    if (response.status === 404) {
      response = await env.ASSETS.fetch(new Request(new URL('/index.html', request.url)));
    }
    return response;
  },
};
