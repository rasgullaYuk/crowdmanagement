"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle, Activity, Users, MapPin, Clock } from "lucide-react"

interface RealTimeUpdate {
  id: string
  type: "crowd" | "incident" | "system" | "prediction"
  severity: "low" | "medium" | "high" | "critical"
  message: string
  location?: string
  timestamp: Date
}

interface RealTimeUpdatesProps {
  context?: "user" | "responder" | "admin"
}

export function RealTimeUpdates({ context = "user" }: RealTimeUpdatesProps) {
  const [updates, setUpdates] = useState<RealTimeUpdate[]>([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    // Mock WebSocket connection
    setIsConnected(true)

    // Simulate real-time updates
    const interval = setInterval(() => {
      const mockUpdates = generateMockUpdate(context)
      if (mockUpdates) {
        setUpdates((prev) => [mockUpdates, ...prev.slice(0, 9)]) // Keep last 10 updates
      }
    }, 8000) // New update every 8 seconds

    return () => {
      clearInterval(interval)
      setIsConnected(false)
    }
  }, [context])

  const generateMockUpdate = (context: string): RealTimeUpdate | null => {
    const updateTypes = {
      user: [
        {
          type: "crowd" as const,
          severity: "medium" as const,
          message: "Crowd density at Main Stage increased to 88%",
          location: "Main Stage",
        },
        {
          type: "prediction" as const,
          severity: "low" as const,
          message: "Peak crowd expected in Food Court in 12 minutes",
          location: "Food Court",
        },
        {
          type: "incident" as const,
          severity: "high" as const,
          message: "Medical emergency reported - responders dispatched",
          location: "VIP Area",
        },
      ],
      responder: [
        {
          type: "incident" as const,
          severity: "critical" as const,
          message: "New high-priority incident assigned to your zone",
          location: "Main Stage",
        },
        {
          type: "system" as const,
          severity: "medium" as const,
          message: "Backup requested for incident MED-003",
          location: "Food Court",
        },
        {
          type: "crowd" as const,
          severity: "high" as const,
          message: "Crowd control needed at Entrance B",
          location: "Entrance B",
        },
      ],
      admin: [
        {
          type: "system" as const,
          severity: "medium" as const,
          message: "CCTV Camera 12 connection restored",
          location: "Parking Lot",
        },
        {
          type: "crowd" as const,
          severity: "critical" as const,
          message: "Multiple zones approaching capacity limits",
          location: "Multiple Zones",
        },
        {
          type: "prediction" as const,
          severity: "high" as const,
          message: "AI model predicts bottleneck at Gate A in 8 minutes",
          location: "Gate A",
        },
      ],
    }

    const contextUpdates = updateTypes[context] || updateTypes.user
    const randomUpdate = contextUpdates[Math.floor(Math.random() * contextUpdates.length)]

    return {
      id: Date.now().toString(),
      ...randomUpdate,
      timestamp: new Date(),
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "border-destructive text-destructive"
      case "high":
        return "border-warning text-warning"
      case "medium":
        return "border-primary text-primary"
      case "low":
        return "border-success text-success"
      default:
        return "border-muted text-muted-foreground"
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "crowd":
        return <Users className="h-4 w-4" />
      case "incident":
        return <AlertTriangle className="h-4 w-4" />
      case "system":
        return <Activity className="h-4 w-4" />
      case "prediction":
        return <Clock className="h-4 w-4" />
      default:
        return <Activity className="h-4 w-4" />
    }
  }

  if (updates.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-4 text-center">
          <Activity className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            {isConnected ? "Monitoring for real-time updates..." : "Connecting to real-time feed..."}
          </p>
          <Badge variant="outline" className={isConnected ? "bg-success/10 text-success border-success/20" : ""}>
            {isConnected ? "Connected" : "Connecting..."}
          </Badge>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">Real-time Updates</h3>
        <Badge variant="outline" className="bg-success/10 text-success border-success/20">
          Live
        </Badge>
      </div>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {updates.map((update) => (
          <Alert key={update.id} className={`border-l-4 ${getSeverityColor(update.severity)}`}>
            <div className="flex items-start space-x-2">
              {getTypeIcon(update.type)}
              <div className="flex-1">
                <AlertDescription className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{update.message}</span>
                    {update.location && (
                      <div className="flex items-center space-x-1 mt-1 text-xs text-muted-foreground">
                        <MapPin className="h-3 w-3" />
                        <span>{update.location}</span>
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap ml-2">
                    {update.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </AlertDescription>
              </div>
            </div>
          </Alert>
        ))}
      </div>
    </div>
  )
}
