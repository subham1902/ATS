const backend = process.env.ATS_BACKEND_ORIGIN || "http://127.0.0.1:8000";
const nextConfig = {
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${backend}/v1/:path*` },
      { source: "/health/:path*", destination: `${backend}/health/:path*` },
    ];
  },
};
export default nextConfig;
