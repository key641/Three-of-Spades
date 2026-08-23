# Drifto Beta 前端设计系统与 UI 开发规范 (Design System)

> 适用范围：Drifto（Three-of-Spades）全站前端开发与 UI 交互实现。
> 核心气质：**Vibrant Travel & Energetic Fresh（活泼能量出行）· 清爽通透 · 极简灵动**。

---

## ⚠️ 铁律零：严格禁用 Emoji（Strictly No Emojis）

1. **绝对禁止在 UI 界面、标签、按钮、标题、分类中使用系统彩色 Emoji**（如 🚶、🍜、✨、🟢、💬、⚙️、👶、💰、⭐ 等）。
2. **所有图标统一使用专业的矢量线条图标库（`lucide-react`）**：
   - 统一图标描边线宽：`strokeWidth={1.75}` 或 `strokeWidth={2}`；
   - 统一图标尺寸：胶囊标签内 `size={13~14}`，按钮内 `size={16~18}`，顶栏按钮 `size={20}`；
   - 颜色继承父级文本色（`currentColor`）或指定的语义变量色。
3. **为什么禁用 Emoji**：
   - Emoji 在不同操作系统（iOS / Android / Windows / macOS）上渲染样式不一致，破坏视觉统一性；
   - 彩色 Emoji 带有廉价感与玩具感，与我们追求的“现代极简、高级专业”视觉调性严重冲突。

---

## 一、 色彩系统规范 (Vibrant Travel & Fresh Palette)

### 1. 品牌活力核心色系
- **品牌主色（能量薄荷绿 / Mint Green）**：`#38c98a`（深态 `#1ea36c`，浅背景 `rgba(56, 201, 138, 0.14)`，微光 `rgba(56, 201, 138, 0.40)`）。
- **活力点缀副色（阳光橙 / Sunny Orange）**：`#FF7A45`（用于高能行动按键如“新建行程”、高亮选中态）。
- **活力明黄（Amber / Sunshine）**：`#f5c842`（用于背景氛围暖光）。

### 2. 背景与文字体系
- **清爽活力背景底色（Fresh Mist）**：`#f4faf6`（清爽透亮，充满出行生机）。
- **深墨绿正文（Deep Forest Ink）**：`#132a20`（高对比度，清晰利落）。
- **次级文本（Fresh Muted）**：`#628073`。

---

## 二、 材质、光影与质感规范 (Textures & Materials)

1. **轻量纸质微粒噪点 (0.08 Subtle Grain Overlay)**：
   - 保留极轻微的微粒纸质触感，避免纯扁平塑料感，同时保持视觉极其透亮清爽。
2. **充满生机的薄荷与阳光呼吸光斑 (Energetic Glow Blobs)**：
   - 背景层使用 80px 高斯模糊的活泼光斑（薄荷绿 `#38c98a` + 阳光橙 `#FF7A45` + 阳光黄 `#f5c842`），慢速浮动带来活力感。
3. **通透毛玻璃 (Crisp Glassmorphism)**：
   - 抽屉与输入栏：`backdrop-filter: blur(28px)` + `background: rgba(255, 255, 255, 0.94)` + `border: 1.5px solid rgba(255, 255, 255, 0.98)`。
4. **绿色调高能光晕阴影 (Energetic Shadows)**：
   - 主按钮与聚焦框带有薄荷绿与橙色微光漫反射阴影（`rgba(56, 201, 138, 0.35)`）。

---

## 三、 动态缓动与签名动效 (Motion Signature)

1. **灵动弹性缓动**：
   - 统一采用曲线：`cubic-bezier(0.16, 1, 0.3, 1)`（超高弹性流畅阻尼）；
   - 按钮 hover / active 变换、抽屉展开、卡片悬浮统一应用 `transition: all 0.25s var(--ease-spring)`。
2. **触觉按压反馈 (Haptic Press Feedback)**：
   - 所有可点击按钮、胶囊标签统一配置按压缩放反馈：`active: scale(0.92 ~ 0.95)`。

---

## 四、 规范遵守 Checklist

在编写任何前端代码或提交修改前，必须自检以下 4 项：
- [ ] **1. 全站无任何 Emoji 表情字符？**（必须全部采用 Lucide 矢量图标）
- [ ] **2. 遵循活泼能量出行配色（薄荷绿 `#38c98a` + 阳光橙 `#FF7A45` + 清爽透亮底 `#f4faf6`）？**
- [ ] **3. 容器与按钮均具备灵动大圆角与通透毛玻璃质感？**
- [ ] **4. 动效曲线严格遵循 `cubic-bezier(0.16, 1, 0.3, 1)`？**
