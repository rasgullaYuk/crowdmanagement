"use client"

import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Shield, ArrowLeft, MapPin, Calendar, Phone } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

export default function RegisterPage() {
  const [step, setStep] = useState<"basic" | "venue" | "contacts" | "success">("basic")
  const [eventData, setEventData] = useState({
    name: "",
    startDate: "",
    endDate: "",
    expectedCrowd: "",
    description: "",
    venueName: "",
    venueAddress: "",
    zones: "",
    cctvPositions: "",
    organizerName: "",
    organizerEmail: "",
    organizerPhone: "",
    emergencyContact: "",
    medicalContact: "",
    securityContact: "",
  })
  const router = useRouter()

  const handleNext = () => {
    if (step === "basic") setStep("venue")
    else if (step === "venue") setStep("contacts")
    else if (step === "contacts") {
      // Mock registration - in real app, save to database
      setStep("success")
    }
  }

  const handleBack = () => {
    if (step === "venue") setStep("basic")
    else if (step === "contacts") setStep("venue")
  }

  const isStepValid = () => {
    switch (step) {
      case "basic":
        return eventData.name && eventData.startDate && eventData.endDate && eventData.expectedCrowd
      case "venue":
        return eventData.venueName && eventData.venueAddress && eventData.zones
      case "contacts":
        return eventData.organizerName && eventData.organizerEmail && eventData.organizerPhone
      default:
        return false
    }
  }

  if (step === "success") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md text-center">
          <CardHeader>
            <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <Shield className="h-8 w-8 text-success" />
            </div>
            <CardTitle className="text-2xl">Event Registered Successfully!</CardTitle>
            <CardDescription>Your event has been created and is ready for monitoring</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <h3 className="font-semibold mb-2">{eventData.name}</h3>
              <p className="text-sm text-muted-foreground">
                {eventData.startDate} - {eventData.endDate}
              </p>
              <p className="text-sm text-muted-foreground">{eventData.venueName}</p>
            </div>
            <Button onClick={() => router.push("/auth/login")} className="w-full">
              Access Event Dashboard
            </Button>
            <Button variant="outline" onClick={() => router.push("/")} className="w-full">
              Return to Home
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center space-x-2 text-primary hover:text-primary/80 mb-4">
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Home</span>
          </Link>
          <div className="flex items-center justify-center space-x-2 mb-4">
            <Shield className="h-8 w-8 text-primary" />
            <span className="text-2xl font-bold">CrowdGuard</span>
          </div>
          <h1 className="text-3xl font-bold mb-2">Register New Event</h1>
          <p className="text-muted-foreground">Set up comprehensive crowd monitoring for your event</p>
        </div>

        {/* Progress Indicator */}
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center space-x-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === "basic" ? "bg-primary text-primary-foreground" : "bg-success text-success-foreground"
              }`}
            >
              1
            </div>
            <div className="w-12 h-0.5 bg-border"></div>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === "venue"
                  ? "bg-primary text-primary-foreground"
                  : step === "contacts"
                    ? "bg-success text-success-foreground"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              2
            </div>
            <div className="w-12 h-0.5 bg-border"></div>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === "contacts" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}
            >
              3
            </div>
          </div>
        </div>

        {step === "basic" && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Calendar className="h-5 w-5" />
                <span>Basic Event Information</span>
              </CardTitle>
              <CardDescription>Provide essential details about your event</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Event Name *</Label>
                  <Input
                    id="name"
                    placeholder="Summer Music Festival 2025"
                    value={eventData.name}
                    onChange={(e) => setEventData({ ...eventData, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="expectedCrowd">Expected Crowd Size *</Label>
                  <Select
                    value={eventData.expectedCrowd}
                    onValueChange={(value) => setEventData({ ...eventData, expectedCrowd: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select crowd size" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="small">Small (&lt; 1,000)</SelectItem>
                      <SelectItem value="medium">Medium (1,000 - 10,000)</SelectItem>
                      <SelectItem value="large">Large (10,000 - 50,000)</SelectItem>
                      <SelectItem value="massive">Massive (50,000+)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="startDate">Start Date *</Label>
                  <Input
                    id="startDate"
                    type="datetime-local"
                    value={eventData.startDate}
                    onChange={(e) => setEventData({ ...eventData, startDate: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="endDate">End Date *</Label>
                  <Input
                    id="endDate"
                    type="datetime-local"
                    value={eventData.endDate}
                    onChange={(e) => setEventData({ ...eventData, endDate: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Event Description</Label>
                <Textarea
                  id="description"
                  placeholder="Describe your event, special considerations, and safety requirements..."
                  value={eventData.description}
                  onChange={(e) => setEventData({ ...eventData, description: e.target.value })}
                />
              </div>
              <Button onClick={handleNext} disabled={!isStepValid()} className="w-full">
                Continue to Venue Details
              </Button>
            </CardContent>
          </Card>
        )}

        {step === "venue" && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <MapPin className="h-5 w-5" />
                <span>Venue & Zone Configuration</span>
              </CardTitle>
              <CardDescription>Configure venue layout and monitoring zones</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="venueName">Venue Name *</Label>
                <Input
                  id="venueName"
                  placeholder="Central Park Amphitheater"
                  value={eventData.venueName}
                  onChange={(e) => setEventData({ ...eventData, venueName: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="venueAddress">Venue Address *</Label>
                <Input
                  id="venueAddress"
                  placeholder="123 Main Street, City, State 12345"
                  value={eventData.venueAddress}
                  onChange={(e) => setEventData({ ...eventData, venueAddress: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="zones">Monitoring Zones *</Label>
                <Textarea
                  id="zones"
                  placeholder="List monitoring zones (e.g., Main Stage, Food Court, Entrance A, VIP Area, Parking Lot 1)"
                  value={eventData.zones}
                  onChange={(e) => setEventData({ ...eventData, zones: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cctvPositions">CCTV Camera Positions</Label>
                <Textarea
                  id="cctvPositions"
                  placeholder="Describe camera locations and coverage areas for optimal monitoring"
                  value={eventData.cctvPositions}
                  onChange={(e) => setEventData({ ...eventData, cctvPositions: e.target.value })}
                />
              </div>
              <div className="flex space-x-2">
                <Button variant="outline" onClick={handleBack} className="flex-1 bg-transparent">
                  Back
                </Button>
                <Button onClick={handleNext} disabled={!isStepValid()} className="flex-1">
                  Continue to Contacts
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === "contacts" && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Phone className="h-5 w-5" />
                <span>Emergency Contacts & Responders</span>
              </CardTitle>
              <CardDescription>Set up contact information for event coordination</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="organizerName">Organizer Name *</Label>
                  <Input
                    id="organizerName"
                    placeholder="John Smith"
                    value={eventData.organizerName}
                    onChange={(e) => setEventData({ ...eventData, organizerName: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="organizerPhone">Organizer Phone *</Label>
                  <Input
                    id="organizerPhone"
                    placeholder="+1 (555) 123-4567"
                    value={eventData.organizerPhone}
                    onChange={(e) => setEventData({ ...eventData, organizerPhone: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="organizerEmail">Organizer Email *</Label>
                <Input
                  id="organizerEmail"
                  type="email"
                  placeholder="organizer@event.com"
                  value={eventData.organizerEmail}
                  onChange={(e) => setEventData({ ...eventData, organizerEmail: e.target.value })}
                />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="emergencyContact">Emergency Coordinator</Label>
                  <Input
                    id="emergencyContact"
                    placeholder="+1 (555) 911-0000"
                    value={eventData.emergencyContact}
                    onChange={(e) => setEventData({ ...eventData, emergencyContact: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="medicalContact">Medical Team Lead</Label>
                  <Input
                    id="medicalContact"
                    placeholder="+1 (555) 123-MEDS"
                    value={eventData.medicalContact}
                    onChange={(e) => setEventData({ ...eventData, medicalContact: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="securityContact">Security Team Lead</Label>
                <Input
                  id="securityContact"
                  placeholder="+1 (555) 123-SAFE"
                  value={eventData.securityContact}
                  onChange={(e) => setEventData({ ...eventData, securityContact: e.target.value })}
                />
              </div>
              <div className="flex space-x-2">
                <Button variant="outline" onClick={handleBack} className="flex-1 bg-transparent">
                  Back
                </Button>
                <Button onClick={handleNext} disabled={!isStepValid()} className="flex-1">
                  Register Event
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="text-center mt-6">
          <p className="text-sm text-muted-foreground">
            Already have an event?{" "}
            <Link href="/auth/login" className="text-primary hover:underline">
              Login here
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
