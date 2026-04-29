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

    const anomalies = await DatabaseService.getAnomalyDetections(eventId, status || undefined)

    return NextResponse.json({ anomalies })
  } catch (error) {
    console.error("Error fetching anomalies:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}
