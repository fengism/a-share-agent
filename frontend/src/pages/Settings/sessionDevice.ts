/** 从 User-Agent 粗略识别设备类型/系统/浏览器，用于"这设备是不是我"的快速判断。 */
export interface DeviceDescription {
  icon: "mobile" | "desktop";
  label: string;
}

export function describeUserAgent(userAgent: string): DeviceDescription {
  const ua = userAgent || "";
  if (!ua) return { icon: "desktop", label: "未知设备" };
  const mobile = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS/i.test(ua);
  const browser = /Edg\//i.test(ua)
    ? "Edge"
    : /Chrome\//i.test(ua)
      ? "Chrome"
      : /Firefox\//i.test(ua)
        ? "Firefox"
        : /Safari\//i.test(ua)
          ? "Safari"
          // 移动端 Safari 的 UA 往往只有 AppleWebKit + Mobile/xxx，没有 Safari/ 标记
          : /AppleWebKit\//i.test(ua)
            ? "Safari"
            : /curl|python|httpx|Go-http/i.test(ua)
              ? "脚本客户端"
              : "未知浏览器";
  // 顺序关键：iPhone/iPad 的 UA 里也含 "like Mac OS X"，必须先判 iOS
  const os = /iPhone|iPad|iPod/i.test(ua)
    ? "iOS"
    : /Android/i.test(ua)
      ? "Android"
      : /Windows/i.test(ua)
        ? "Windows"
        : /Macintosh|Mac OS X/i.test(ua)
          ? "macOS"
          : /Linux/i.test(ua)
            ? "Linux"
            : "";
  return { icon: mobile ? "mobile" : "desktop", label: os ? `${os} · ${browser}` : browser };
}
