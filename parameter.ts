import { ComfyUIStackProps } from "./lib/comfyui-stack";

export const defaultParameter: ComfyUIStackProps = {
  cheapVpc: true,
  useSpot: true,
  spotPrice: "0.752",
  autoScaleDown: true,
  scheduleAutoScaling: false,
  timezone: "UTC",
  scheduleScaleDown: "0 9 * * 1-5",
  scheduleScaleUp: "0 18 * * *",
  selfSignUpEnabled: false,
  allowedSignUpEmailDomains: undefined,
  mfaRequired: false,
  samlAuthEnabled: false,
  allowedIpV4AddressRanges: undefined,
  allowedIpV6AddressRanges: undefined,
  hostName: undefined,
  domainName: undefined,
  hostedZoneId: undefined,
};

export const overrideParameter: Partial<ComfyUIStackProps> = {
  // example

  // autoScaleDown: false,
  // scheduleAutoScaling: true,
  // timezone: "Asia/Tokyo",
  // scheduleScaleUp: "0 8 * * 1-5",
  // scheduleScaleDown: "0 19 * * *",
  // selfSignUpEnabled: true,
  // allowedSignUpEmailDomains: ["amazon.com"],
};
