import { NextRequest, NextResponse } from 'next/server'
import nodemailer from 'nodemailer'

export async function POST(req: NextRequest) {
  const { method, name, email, subject, message } = await req.json()

  /* ── TELEGRAM ─────────────────────────────────────────────────── */
  if (method === 'telegram') {
    const token  = process.env.TELEGRAM_BOT_TOKEN
    const chatId = process.env.TELEGRAM_CHAT_ID

    if (!token || !chatId) {
      return NextResponse.json(
        { error: 'Telegram credentials not configured.' },
        { status: 500 }
      )
    }

    const text =
      `📩 <b>New Portfolio Message</b>\n\n` +
      `👤 <b>From:</b> ${name}\n` +
      `📧 <b>Email:</b> ${email}\n` +
      `📌 <b>Subject:</b> ${subject}\n\n` +
      `💬 <b>Message:</b>\n${message}`

    const res  = await fetch(
      `https://api.telegram.org/bot${token}/sendMessage`,
      {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' }),
      }
    )
    const data = await res.json()

    if (!data.ok) {
      return NextResponse.json({ error: data.description }, { status: 500 })
    }
    return NextResponse.json({ success: true, via: 'Telegram' })
  }

  /* ── EMAIL via Gmail SMTP (Nodemailer) ────────────────────────── */
  if (method === 'email') {
    const gmailUser = process.env.GMAIL_USER
    const gmailPass = process.env.GMAIL_APP_PASSWORD

    if (!gmailUser || !gmailPass) {
      return NextResponse.json(
        { error: 'Email credentials not configured. Add GMAIL_USER and GMAIL_APP_PASSWORD to .env.local' },
        { status: 500 }
      )
    }

    const transporter = nodemailer.createTransport({
      service: 'gmail',
      auth: { user: gmailUser, pass: gmailPass },
    })

    await transporter.sendMail({
      from:    `"${name} via Portfolio" <${gmailUser}>`,
      replyTo: email,
      to:      'sherzodusmonjonov734@gmail.com',
      subject: `[Portfolio] ${subject} — from ${name}`,
      html: `
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto;background:#0a1628;padding:32px;border-radius:16px;color:#e2e8f0">
          <h2 style="color:#38bdf8;margin:0 0 24px">📩 New Portfolio Message</h2>
          <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
            <tr><td style="padding:8px 0;color:#94a3b8;width:80px">From</td><td style="padding:8px 0;color:#fff;font-weight:600">${name}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8">Email</td><td style="padding:8px 0"><a href="mailto:${email}" style="color:#38bdf8">${email}</a></td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8">Subject</td><td style="padding:8px 0;color:#fff">${subject}</td></tr>
          </table>
          <div style="background:#0d1b2e;border-left:3px solid #38bdf8;padding:16px 20px;border-radius:8px;color:#cbd5e1;line-height:1.7;white-space:pre-wrap">${message}</div>
          <p style="margin-top:24px;color:#475569;font-size:12px">Sent via your portfolio contact form</p>
        </div>
      `,
    })

    return NextResponse.json({ success: true, via: 'Email' })
  }

  return NextResponse.json({ error: 'Unknown method' }, { status: 400 })
}
