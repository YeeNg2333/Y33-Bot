// 无头 MC 客户端（保持在线版，卡 t_5bccfcd8）
// 用法: node client_hold.js [host] [port] [username] [保持秒数]
// 用途：保持在线 N 秒并打印收到的所有聊天/系统消息 —— 用来验证 QQ→MC 的 tellraw 注入真的在游戏内可见
const mineflayer = require('mineflayer')

const host = process.argv[2] || '127.0.0.1'
const port = parseInt(process.argv[3] || '25610', 10)
const username = process.argv[4] || 'Watcher'
const holdSec = parseInt(process.argv[5] || '25', 10)

console.log(`[hold] 连接 ${host}:${port} 用户名 ${username} 保持 ${holdSec}s`)
const bot = mineflayer.createBot({ host, port, username, auth: 'offline' })

let spawned = false
bot.once('spawn', () => {
  spawned = true
  console.log('[hold] 已 spawn（进服成功），版本协商: ' + (bot.version || '?'))
})
bot.on('message', (jsonMsg) => {
  const t = new Date().toISOString().substring(11, 19)
  console.log(`[hold ${t}] 收到: ${jsonMsg.toString()}`)
})
bot.on('kicked', (r) => console.log('[hold] 被踢出: ' + JSON.stringify(r)))
bot.on('error', (e) => console.log('[hold] 出错: ' + e.message))
bot.on('end', () => console.log('[hold] 连接结束'))

setTimeout(() => {
  console.log('[hold] 保持结束，主动退出（spawned=' + spawned + '）')
  try { bot.quit('bye') } catch (e) { /* ignore */ }
  setTimeout(() => process.exit(spawned ? 0 : 4), 800)
}, holdSec * 1000)
