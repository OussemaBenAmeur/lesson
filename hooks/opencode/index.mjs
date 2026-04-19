import { spawn } from 'node:child_process'
import path from 'node:path'

const homeDir = process.env.HOME || ''
const bridgePath =
  process.env.LESSON_OPENCODE_BRIDGE ||
  path.join(homeDir, '.local', 'share', 'lesson', 'opencode_bridge.py')

function forward(kind, payload) {
  try {
    const child = spawn('python3', [bridgePath, kind], {
      stdio: ['pipe', 'ignore', 'ignore'],
      detached: true,
    })
    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
    child.unref()
  } catch {
    return
  }
}

function normalizePayload(event) {
  const sessionId = event?.session?.id || event?.sessionId || null
  const cwd =
    event?.cwd ||
    event?.workspaceRoot ||
    event?.session?.cwd ||
    process.cwd()

  if (event?.type === 'tool.after') {
    return {
      cwd,
      session_id: sessionId,
      tool_call_id: event?.toolCallId || event?.tool?.callId || null,
      tool_name: event?.tool?.name || event?.toolName || 'unknown',
      tool_input: event?.tool?.input || event?.toolInput || {},
      tool_response: event?.tool?.output || event?.toolOutput || {},
    }
  }

  return {
    cwd,
    session_id: sessionId,
    stop_hook_active: false,
  }
}

const plugin = {
  name: 'lesson',
  async onEvent(event) {
    if (!event || !event.type) {
      return
    }

    if (event.type === 'tool.after') {
      forward('postToolUse', normalizePayload(event))
      return
    }

    if (event.type === 'session.start') {
      forward('sessionStart', normalizePayload(event))
      return
    }

    if (event.type === 'session.idle' || event.type === 'session.end') {
      forward('stop', normalizePayload(event))
    }
  },
}

export default plugin
