import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService } from "@/lib/database"

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const eventId = searchParams.get("eventId")
    const status = searchParams.get("status")

    if (!eventId) {
      return NextResponse.json({ error: "Event ID is required" }, { status: 400 })
    }

    const lostPersons = await DatabaseService.getLostPersons(eventId, status || undefined)

    return NextResponse.json({ lostPersons })
  } catch (error) {
    console.error("Error fetching lost persons:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const lostPerson = await DatabaseService.createLostPersonReport(body)

    if (!lostPerson) {
      return NextResponse.json({ error: "Failed to create lost person report" }, { status: 500 })
    }

    return NextResponse.json({ lostPerson }, { status: 201 })
  } catch (error) {
    console.error("Error creating lost person report:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}
