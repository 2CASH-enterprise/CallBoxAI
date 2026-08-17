/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // "standalone" : produit un serveur Node autonome et léger, idéal pour Docker
  // (voir frontend/Dockerfile et section 27 du cahier des charges).
  output: "standalone",
};

module.exports = nextConfig;
