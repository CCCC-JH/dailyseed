/**
 * 毕业卡的图：纯前端 Canvas 画出来，不依赖任何后端接口，也不引第三方库。
 *
 * 版式故意克制——一张卡片、一句卡面文字、一行"留住 N 次 · 某月某日宣布毕业"、
 * 底部一行产品名。不放二维码、不放"快来用"的号召：分享图不是广告位，
 * 它的作用是让宣布毕业这件事有个可以留存的形状。
 */

export interface DrawInput {
  /** 卡面原文（今天那一粒那句话） */
  text: string
  /** 留住次数 */
  keptCount: number
  /** 分类，例如「注意力」 */
  category: string
  /** 宣布毕业的日期 yyyy-MM-dd */
  graduatedDate: string
}

const W = 1080
const H = 1440

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** 按宽度折行（中文逐字测宽，不依赖空格分词） */
function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const ch of text) {
    if (ch === '\n') {
      lines.push(line)
      line = ''
      continue
    }
    const next = line + ch
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line)
      line = ch
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  if (!y || !m || !d) return iso
  return `${y} 年 ${Number(m)} 月 ${Number(d)} 日`
}

export const SHARE_WIDTH = W
export const SHARE_HEIGHT = H

/** 画一张毕业卡（字体要事先加载好，否则会退回系统字体） */
export function drawGraduationCard(canvas: HTMLCanvasElement, input: DrawInput): void {
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = W * ratio
  canvas.height = H * ratio
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)

  const FAMILY = '"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif'

  // 底：深色 + 两处极淡的光
  const bg = ctx.createLinearGradient(0, 0, W, H)
  bg.addColorStop(0, '#0c1013')
  bg.addColorStop(1, '#07090b')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)

  const glowTop = ctx.createRadialGradient(W * 0.5, -60, 0, W * 0.5, -60, 820)
  glowTop.addColorStop(0, 'rgba(95,216,164,0.20)')
  glowTop.addColorStop(1, 'rgba(95,216,164,0)')
  ctx.fillStyle = glowTop
  ctx.fillRect(0, 0, W, H * 0.72)

  const glowBottom = ctx.createRadialGradient(W * 0.92, H + 40, 0, W * 0.92, H + 40, 700)
  glowBottom.addColorStop(0, 'rgba(233,196,106,0.13)')
  glowBottom.addColorStop(1, 'rgba(233,196,106,0)')
  ctx.fillStyle = glowBottom
  ctx.fillRect(0, 0, W, H)

  // 卡片本体
  const pad = 84
  const cardX = pad
  const cardY = 190
  const cardW = W - pad * 2
  const cardH = 900

  ctx.save()
  ctx.shadowColor = 'rgba(0,0,0,0.55)'
  ctx.shadowBlur = 60
  ctx.shadowOffsetY = 26
  roundRect(ctx, cardX, cardY, cardW, cardH, 46)
  const cardFill = ctx.createLinearGradient(cardX, cardY, cardX, cardY + cardH)
  cardFill.addColorStop(0, 'rgba(255,255,255,0.085)')
  cardFill.addColorStop(1, 'rgba(255,255,255,0.035)')
  ctx.fillStyle = cardFill
  ctx.fill()
  ctx.restore()

  ctx.save()
  roundRect(ctx, cardX, cardY, cardW, cardH, 46)
  ctx.strokeStyle = 'rgba(255,255,255,0.13)'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.restore()

  // 卡片顶部一道强调线
  const topLine = ctx.createLinearGradient(cardX + 60, 0, cardX + cardW - 60, 0)
  topLine.addColorStop(0, 'rgba(95,216,164,0)')
  topLine.addColorStop(0.5, 'rgba(95,216,164,0.75)')
  topLine.addColorStop(1, 'rgba(95,216,164,0)')
  ctx.fillStyle = topLine
  ctx.fillRect(cardX + 60, cardY - 1, cardW - 120, 2)

  // 顶部小标
  ctx.fillStyle = '#e9c46a'
  ctx.font = `600 30px ${FAMILY}`
  ctx.textAlign = 'center'
  ctx.fillText('这粒已经长成我的习惯了', W / 2, 122)

  // 卡面文字
  ctx.fillStyle = '#f2f5f3'
  ctx.font = `600 64px ${FAMILY}`
  ctx.textAlign = 'left'
  const lines = wrap(ctx, input.text, cardW - 140)
  let y = cardY + 150
  for (const line of lines.slice(0, 6)) {
    ctx.fillText(line, cardX + 70, y)
    y += 90
  }

  // 中部细线
  y += 26
  ctx.fillStyle = 'rgba(255,255,255,0.12)'
  ctx.fillRect(cardX + 70, y, cardW - 140, 1)

  // 数据行
  y += 76
  ctx.fillStyle = '#a9b4b0'
  ctx.font = `400 34px ${FAMILY}`
  ctx.fillText(`${input.category} · 留住 ${input.keptCount} 次`, cardX + 70, y)

  y += 62
  ctx.fillStyle = '#6d7975'
  ctx.font = `400 32px ${FAMILY}`
  ctx.fillText(`${formatDate(input.graduatedDate)} 宣布毕业`, cardX + 70, y)

  // 一盆长成的植株（简单几何，和前端那个盆同一套语言）
  const cx = W / 2
  const baseY = cardY + cardH - 118
  ctx.fillStyle = 'rgba(255,255,255,0.09)'
  ctx.beginPath()
  ctx.ellipse(cx, baseY + 74, 116, 20, 0, 0, Math.PI * 2)
  ctx.fill()

  const bowl = ctx.createLinearGradient(cx - 70, baseY, cx + 70, baseY + 90)
  bowl.addColorStop(0, 'rgba(255,255,255,0.24)')
  bowl.addColorStop(1, 'rgba(255,255,255,0.07)')
  ctx.fillStyle = bowl
  roundRect(ctx, cx - 66, baseY, 132, 86, 20)
  ctx.fill()

  const leaf = ctx.createLinearGradient(cx, baseY - 160, cx, baseY)
  leaf.addColorStop(0, '#5fd8a4')
  leaf.addColorStop(1, '#2f9d72')
  ctx.fillStyle = leaf
  const drawLeaf = (angle: number, scale: number, alpha: number) => {
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.translate(cx, baseY)
    ctx.rotate(angle)
    ctx.beginPath()
    ctx.ellipse(0, -78 * scale, 30 * scale, 80 * scale, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }
  drawLeaf(0, 1, 1)
  drawLeaf(-0.42, 0.88, 0.88)
  drawLeaf(0.42, 0.88, 0.76)

  // 底部产品名：只写名字，不写口号
  ctx.textAlign = 'center'
  ctx.fillStyle = 'rgba(255,255,255,0.34)'
  ctx.font = `500 32px ${FAMILY}`
  ctx.fillText('每日一粒 · DailySeed', W / 2, H - 96)
}

/** 转成可下载 / 可分享的文件 */
export function canvasToFile(canvas: HTMLCanvasElement): Promise<File | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve(null)
        return
      }
      resolve(new File([blob], 'dailyseed-graduated.png', { type: 'image/png' }))
    }, 'image/png')
  })
}
