import { type NextRequest, NextResponse } from "next/server"
import { DatabaseService, isMissingSupabaseConfigError } from "@/lib/database"

export const dynamic = "force-dynamic"

const handleApiError = (error: unknown) => {
  console.error("Error updating incident:", error)

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

export async function PATCH(request: NextRequest, { params }: { params: { id: string } }) {
  try {
    const body = await request.json()
    const { id } = params

    const incident = await DatabaseService.updateIncident(id, body)

    if (!incident) {
      return NextResponse.json({ error: "Incident not found" }, { status: 404 })
    }

    return NextResponse.json({ incident })
  } catch (error) {
    return handleApiError(error)
  }
}
