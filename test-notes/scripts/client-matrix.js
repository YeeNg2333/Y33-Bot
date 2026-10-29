// 原版矩阵用无头客户端（卡 t_ac457fe1）
// 用法: node client-matrix.js <host> <port> <username> [version|-] [plainMsg] [hashMsg]
//   version: 传 '-' 表示交给 mineflayer 自动协商（默认）
// 行为：进服 → 普通聊天 → '#' 聊天 → 退服；打印协商到的版本，便于核对
const mineflayer = require('mineflayer')

const host = process.argv[2] || '127.0.0.1'
const port = parseInt(process.argv[3] || '25600', 10)
const username = process.argv[4] || 'Steve'
const versionArg = process.argv[5] && process.argv[5] !== '-' ? process.argv[5] : null
const plainMsg = process.argv[6] || '矩阵测试：普通聊天（不该被转发）'
const hashMsg = process.argv[7] || '#矩阵测试：带井号聊天（应被转发）'

const opts = { host, port, username, auth: 'offline' }
if (versionArg) opts.version = versionArg
console.log(`[client] 连接 ${host}:${port} 用户 ${username} version=${versionArg || 'auto'}`)

const bot = mineflayer.createBot(opts)

let finished = false
function finish(code) {
  if (finished) return
  finished = true
  try { bot.quit('bye') } catch (e) { /* ignore */ }
  setTimeout(() => process.exit(code), 800)
}

bot.once('spawn', async () => {
  console.log('[client] 已 spawn（进服成功），版本协商: ' + (bot.version || '?'))
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  await sleep(1500)
  bot.chat(plainMsg)
  console.log('[client] 已发送普通聊天')
  await sleep(1200)
  bot.chat(hashMsg)
  console.log('[client] 已发送 # 聊天')
  await sleep(1500)
  console.log('[client] 主动退出')
  finish(0)
})

bot.on('kicked', (reason) => {
  console.log('[client] 被踢出: ' + JSON.stringify(reason))
  finish(2)
})
bot.on('error', (err) => {
  console.log('[client] 出错: ' + err.message)
  finish(1)
})
bot.on('end', () => {
  console.log('[client] 连接结束')
  finish(finished ? 0 : 4)
})

setTimeout(() => {
  console.log('[client] 超时（45s）')
  finish(3)
}, 45000)
