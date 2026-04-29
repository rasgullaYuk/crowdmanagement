import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService, isMissingSupabaseConfigError } from "@/lib/database"

const handleApiError = (context: string, error: unknown) => {
  console.error(context, error)

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

    const lostPersons = await DatabaseService.getLostPersons(eventId, status || undefined)

    return NextResponse.json({ lostPersons })
  } catch (error) {
    return handleApiError("Error fetching lost persons:", error)
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
    return handleApiError("Error creating lost person report:", error)
  }
}
