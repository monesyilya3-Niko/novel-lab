/// <reference types="vite/client" />

// Vite 客户端类型引用（2026-10-12 补）。
//
// 作用：让 import.meta.env（PROD / DEV / MODE 等）在 TS 中有类型。
// 此前项目未引入，故 import.meta.env.PROD 会报 TS2339。
//
// 为什么需要它：globalErrorHandlers 需要判断"是否生产构建"来决定是否安装
// 全局错误兜底（开发环境交给 Vite 的 HMR overlay，重复提示反而干扰）。
