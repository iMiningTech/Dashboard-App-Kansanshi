/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export → drops onto S3 + CloudFront (no server needed).
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};
export default nextConfig;
