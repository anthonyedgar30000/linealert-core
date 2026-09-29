import type { NextConfig } from "next";

const allowedDevOrigin = process.env.LINEALERT_UI_ALLOWED_DEV_ORIGIN?.trim();

const nextConfig: NextConfig = {
  allowedDevOrigins: allowedDevOrigin ? [allowedDevOrigin] : [],
};

export default nextConfig;
