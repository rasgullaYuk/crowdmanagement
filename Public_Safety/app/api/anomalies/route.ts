import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService, isMissingSupabaseConfigError } from "@/lib/database"

const handleApiError = (error: unknown) => {
  console.error("Error fetching anomalies:", error)

  if (isMissingSupabaseConfigError(error)) {
    return NextResponse.json(
      {
        error: "Supabase configuration is missing",
        code: "SUPABASE_CONFIG_MISSING",
        missing: error.missingKeys,
      },
      { status: 503 },
    )
  }

  return NextResponse.json({ error: "Internal server error" }, { status: 500 })
}

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
    return handleApiError(error)
  }
}
