import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService, isMissingSupabaseConfigError } from "@/lib/database"

const handleApiError = (error: unknown) => {
  console.error("Error fetching crowd density:", error)

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
    const zoneId = searchParams.get("zoneId")
    const hours = Number.parseInt(searchParams.get("hours") || "24")

    if (!eventId) {
      return NextResponse.json({ error: "Event ID is required" }, { status: 400 })
    }

    const densityData = await DatabaseService.getCrowdDensityHistory(eventId, zoneId || undefined, hours)

    return NextResponse.json({ densityData })
  } catch (error) {
    return handleApiError(error)
  }
}
