/**
 * MCP 配置在 UI 中的展示前缀（仅高亮区；复制仍使用纯 JSON）。
 * 注释按序号排列，便于扫读。
 */
export function buildMcpConfigDisplaySnippet(jsonBody: string): string {
    const lines = [
        "// (1) musa-knowledge-search：基于上游 npm 包 airweave-mcp-search 的领域定制；",
        "//     协议与运行逻辑一致，description / 包名等为专门场景区分。",
        "// (2) 若使用本地源码而非 npx 安装的包，可改用 node 指向入口（将 <repo-root> 换为你本机仓库根目录）：",
        '//     "command": "node",',
        '//     "args": [',
        '//       "<repo-root>/airweave/mcp-servers/musa-knowledge-search/index.js"',
        "//     ],",
        "//",
    ];
    return `${lines.join("\n")}\n${jsonBody}`;
}
