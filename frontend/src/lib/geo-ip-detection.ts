/**
 * Geo IP Detection - 智能API地址检测
 *
 * 根据当前访问的hostname自动配置最佳的API地址
 */

/**
 * 检测当前是否在本地环境
 */
const isLocalDevelopment = (): boolean => {
  const hostname = window.location.hostname;
  return hostname === 'localhost' || hostname === '127.0.0.1';
};

/**
 * 检测是否为有效的IP地址
 */
const isIPAddress = (hostname: string): boolean => {
  const ipPattern = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
  return ipPattern.test(hostname);
};

/**
 * 验证IP地址的每个部分是否有效
 */
const isValidIPPart = (part: string): boolean => {
  const num = parseInt(part, 10);
  return num >= 0 && num <= 255 && part === num.toString();
};

/**
 * 验证完整的IP地址
 */
const isValidIPAddress = (hostname: string): boolean => {
  const parts = hostname.split('.');
  if (parts.length !== 4) return false;
  return parts.every(isValidIPPart);
};

/**
 * 检测最佳的API URL
 *
 * @returns 检测到的最佳API URL
 */
export const detectBestApiUrl = (): string => {
  const hostname = window.location.hostname;
  const protocol = window.location.protocol; // http: 或 https:

  // 如果是本地开发，使用 localhost
  if (isLocalDevelopment()) {
    return 'http://localhost:8001';
  }

  // 如果是有效的IP地址，使用相同IP的8001端口
  if (isIPAddress(hostname) && isValidIPAddress(hostname)) {
    return `${protocol}//${hostname}:8001`;
  }

  // 如果是域名，使用相同的域名和8001端口
  if (hostname.includes('.')) {
    return `${protocol}//${hostname}:8001`;
  }

  // 默认回退到 localhost
  return 'http://localhost:8001';
};

/**
 * 动态设置全局API配置
 *
 * 这会在页面加载时自动调用，确保所有API请求使用正确的地址
 */
export const setupDynamicApiConfig = (): void => {
  const bestApiUrl = detectBestApiUrl();

  // 设置 window.ENV，优先级最高
  if (!window.ENV) {
    (window as any).ENV = {};
  }

  // 检查当前配置是否为"auto"或不存在
  const currentApiUrl = window.ENV?.API_URL;

  // 如果当前配置是"auto"或者配置不正确，则使用检测到的最佳URL
  if (!currentApiUrl || currentApiUrl === 'auto' || currentApiUrl === '/api') {
    window.ENV.API_URL = bestApiUrl;
    console.log('🟢[Dynamic Config] API_URL auto-detected and set to:', bestApiUrl);
    console.log('🟡[Dynamic Config] Current hostname:', window.location.hostname);
    console.log('🟡[Dynamic Config] Current origin:', window.location.origin);
    console.log('🟡[Dynamic Config] Protocol:', window.location.protocol);
  } else {
    console.log('🟣[Dynamic Config] API_URL already configured:', currentApiUrl);
    console.log('🟣[Dynamic Config] Skipping auto-detection');
  }
};