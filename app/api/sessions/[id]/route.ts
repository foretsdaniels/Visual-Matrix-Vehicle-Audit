import { NextRequest, NextResponse } from "next/server"
import { deleteSession, getSession } from "@/lib/store"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const session = getSession(id)

  if (!session) {
    return NextResponse.json({ error: "Session not found" }, { status: 404 })
  }

  deleteSession(id)
  return NextResponse.json({ status: "deleted", sessionId: id })
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const session = getSession(id)

  if (!session) {
    return NextResponse.json({ error: "Session not found" }, { status: 404 })
  }

  return NextResponse.json(session)
}
