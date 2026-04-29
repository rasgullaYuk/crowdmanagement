import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService } from "@/lib/database"

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const eventId = searchParams.get("eventId")
    const status = searchParams.get("status")
    const assignedTo = searchParams.get("assignedTo")

    if (!eventId) {
      return NextResponse.json({ error: "Event ID is required" }, { status: 400 })
    }

    const incidents = await DatabaseService.getIncidents(eventId, status || undefined, assignedTo || undefined)

    return NextResponse.json({ incidents })
  } catch (error) {
    console.error("Error fetching incidents:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Generate incident ID based on type
    const typePrefix = body.type.toLowerCase().includes("medical")
      ? "MED"
      : body.type.toLowerCase().includes("security")
        ? "SEC"
        : body.type.toLowerCase().includes("fire")
          ? "FIRE"
          : "TECH"

    const incidentId = `${typePrefix}-${Date.now().toString().slice(-6)}`

    const incident = await DatabaseService.createIncident({
      ...body,
      incident_id: incidentId,
      reported_at: new Date().toISOString(),
    })

    if (!incident) {
      return NextResponse.json({ error: "Failed to create incident" }, { status: 500 })
    }

    return NextResponse.json({ incident }, { status: 201 })
  } catch (error) {
    console.error("Error creating incident:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}
