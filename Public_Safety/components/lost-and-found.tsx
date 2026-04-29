"use client"

import React, { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Search, MapPin, Phone, Clock, Upload, User, CheckCircle, FileText, Video, AlertTriangle, ArrowLeft, Play, Pause, Scan } from "lucide-react"
import { toast } from "sonner"

interface LostPerson {
    id: string
    name: string
    age: number
    description: string
    last_seen: string
    contact: string
    image_url: string | null
    status: "active" | "found"
    reported_at: string
    found_location?: string
}

interface Match {
    person_id: string
    zone_id: string
    confidence: number
    description: string
    timestamp: string
    found_at: string
    image_url?: string
    found_frame_url?: string
}

export function LostAndFound({ userType = "user" }: { userType?: "user" | "admin" }) {
    const [view, setView] = useState<"menu" | "report" | "cases" | "analysis">("menu")
    const [reports, setReports] = useState<LostPerson[]>([])
    const [matches, setMatches] = useState<Match[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [analysisResult, setAnalysisResult] = useState<any>(null)

    // Video Analysis State
    const [videoFile, setVideoFile] = useState<File | null>(null)
    const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const videoRef = useRef<HTMLVideoElement>(null)

    // Form state
    const [formData, setFormData] = useState({
        name: "",
        age: "",
        description: "",
        last_seen: "",
        contact: "",
        image: null as File | null
    })

    const fetchReports = async () => {
        try {
            const res = await fetch("http://localhost:5000/api/lost-found/reports")
            if (res.ok) {
                const data = await res.json()
                setReports(data.reports)
            }
        } catch (error) {
            console.error("Error fetching reports:", error)
        }
    }

    const fetchMatches = async () => {
        try {
            const res = await fetch("http://localhost:5000/api/lost-found/matches")
            if (res.ok) {
                const data = await res.json()
                setMatches(data.matches)
            }
        } catch (error) {
            console.error("Error fetching matches:", error)
        }
    }

    useEffect(() => {
        fetchReports()
        fetchMatches()

        // Poll for updates
        const interval = setInterval(() => {
            fetchReports()
            fetchMatches()
        }, 30000)

        return () => clearInterval(interval)
    }, [])

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target
        setFormData(prev => ({ ...prev, [name]: value }))
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFormData(prev => ({ ...prev, image: e.target.files![0] }))
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsLoading(true)

        try {
            const data = new FormData()
            data.append("name", formData.name)
            data.append("age", formData.age)
            data.append("description", formData.description)
            data.append("last_seen", formData.last_seen)
            data.append("contact", formData.contact)
            if (formData.image) {
                data.append("image", formData.image)
            }

            const res = await fetch("http://localhost:5000/api/lost-found/report", {
                method: "POST",
                body: data
            })

            if (res.ok) {
                toast.success("Report submitted successfully")
                setFormData({
                    name: "",
                    age: "",
                    description: "",
                    last_seen: "",
                    contact: "",
                    image: null
                })
                fetchReports()
                setView("cases")
            } else {
                toast.error("Failed to submit report")
            }
        } catch (error) {
            console.error("Error submitting report:", error)
            toast.error("Error submitting report")
        } finally {
            setIsLoading(false)
        }
    }

    const handleVideoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return

        const file = e.target.files[0]
        setVideoFile(file)
        setVideoPreviewUrl(URL.createObjectURL(file))
        setAnalysisResult(null)
    }

    const startAnalysis = async () => {
        if (!videoFile) return

        setIsAnalyzing(true)
        setAnalysisResult(null)

        // Start playing video to simulate scanning
        if (videoRef.current) {
            videoRef.current.play()
        }

        // Show info toast about processing time
        toast.info("Processing video... This should complete quickly!")

        try {
            const formData = new FormData()
            formData.append("video", videoFile)
            formData.append("zone_id", "manual_upload")

            // Use the quick endpoint that won't crash
            const res = await fetch("http://localhost:5000/api/cameras/upload-video-quick", {
                method: "POST",
                body: formData
            })

            if (res.ok) {
                const data = await res.json()
                setAnalysisResult(data.analysis)
                toast.success("Video analysis complete!")

                // If matches found, handle auto-pause
                if (data.analysis.found_persons && data.analysis.found_persons.length > 0) {
                    const match = data.analysis.found_persons[0]
                    if (match.timestamp && videoRef.current) {
                        // Parse timestamp MM:SS to seconds
                        const parts = match.timestamp.split(':')
                        if (parts.length === 2) {
                            const seconds = parseInt(parts[0]) * 60 + parseInt(parts[1])
                            videoRef.current.currentTime = seconds
                            videoRef.current.pause()
                            toast.success(`✅ Match found at ${match.timestamp}!`, { duration: 5000 })
                        }
                    }
                    fetchMatches()
                } else {
                    toast.info("Analysis complete. No matches found.")
                }
            } else {
                const errorText = await res.text()
                console.error("Server error:", errorText)
                toast.error(`Analysis failed: ${res.status} ${res.statusText}`)
                if (videoRef.current) videoRef.current.pause()
            }
        } catch (error: any) {
            console.error("Error uploading video:", error)

            // Provide more specific error messages
            if (error.name === 'AbortError') {
                toast.error("Video analysis timed out (10 min limit). Try a shorter video.")
            } else if (error.message && error.message.includes('fetch')) {
                toast.error("Cannot connect to server. Make sure the backend is running on port 5000.")
            } else {
                toast.error(`Error: ${error.message || "Failed to upload video"}`)
            }

            if (videoRef.current) videoRef.current.pause()
        } finally {
            setIsAnalyzing(false)
        }
    }

    const generateSaliency = async (imageUrl: string) => {
        toast.info("Generating Saliency Map...")
        try {
            const res = await fetch("http://localhost:5000/api/explain/saliency", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image_url: imageUrl })
            })

            if (res.ok) {
                const data = await res.json()
                window.open(`http://localhost:5000${data.explanation_url}`, '_blank')
                toast.success("Saliency Map Generated!")
            } else {
                toast.error("Failed to generate saliency map")
            }
        } catch (error) {
            console.error("Error generating saliency:", error)
            toast.error("Error generating saliency map")
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Lost & Found</h2>
                    <p className="text-muted-foreground">
                        AI-powered missing person tracking and identification
                    </p>
                </div>
                {view !== "menu" && (
                    <Button variant="outline" onClick={() => setView("menu")} className="gap-2">
                        <ArrowLeft className="h-4 w-4" /> Back to Menu
                    </Button>
                )}
            </div>

            {view === "menu" && (
                <div className="grid md:grid-cols-3 gap-6">
                    <Card className="hover:shadow-lg transition-all cursor-pointer border-blue-200 bg-blue-50/50" onClick={() => setView("report")}>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-blue-700">
                                <User className="h-6 w-6" />
                                Report Missing
                            </CardTitle>
                            <CardDescription>
                                Register a new missing person case with details and photo.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button className="w-full bg-blue-600 hover:bg-blue-700">Start Report</Button>
                        </CardContent>
                    </Card>

                    <Card className="hover:shadow-lg transition-all cursor-pointer border-amber-200 bg-amber-50/50" onClick={() => setView("cases")}>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-amber-700">
                                <FileText className="h-6 w-6" />
                                Active Cases
                            </CardTitle>
                            <CardDescription>
                                View status of all reported missing persons and found matches.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-sm font-medium">Active: {reports.filter(r => r.status === 'active').length}</span>
                                <span className="text-sm font-medium text-green-600">Found: {reports.filter(r => r.status === 'found').length}</span>
                            </div>
                            <Button variant="outline" className="w-full border-amber-600 text-amber-700 hover:bg-amber-100">View Cases</Button>
                        </CardContent>
                    </Card>

                    <Card className="hover:shadow-lg transition-all cursor-pointer border-purple-200 bg-purple-50/50" onClick={() => setView("analysis")}>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-purple-700">
                                <Video className="h-6 w-6" />
                                Video Analysis
                            </CardTitle>
                            <CardDescription>
                                Upload CCTV footage to search for all missing persons using AI.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button variant="outline" className="w-full border-purple-600 text-purple-700 hover:bg-purple-100">Analyze Video</Button>
                        </CardContent>
                    </Card>
                </div>
            )}

            {view === "report" && (
                <Card>
                    <CardHeader>
                        <CardTitle>Report a Lost Person</CardTitle>
                        <CardDescription>
                            Provide details and a photo to help our AI system locate the person.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="name">Full Name</Label>
                                    <Input
                                        id="name"
                                        name="name"
                                        value={formData.name}
                                        onChange={handleInputChange}
                                        required
                                        placeholder="e.g. John Doe"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="age">Age</Label>
                                    <Input
                                        id="age"
                                        name="age"
                                        type="number"
                                        value={formData.age}
                                        onChange={handleInputChange}
                                        required
                                        placeholder="e.g. 10"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="description">Description (Clothing, Height, etc.)</Label>
                                <Textarea
                                    id="description"
                                    name="description"
                                    value={formData.description}
                                    onChange={handleInputChange}
                                    required
                                    placeholder="e.g. Wearing a red t-shirt, blue jeans, white sneakers. Height approx 4ft."
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="last_seen">Last Seen Location</Label>
                                    <Input
                                        id="last_seen"
                                        name="last_seen"
                                        value={formData.last_seen}
                                        onChange={handleInputChange}
                                        placeholder="e.g. Near Food Court entrance"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="contact">Contact Number</Label>
                                    <Input
                                        id="contact"
                                        name="contact"
                                        value={formData.contact}
                                        onChange={handleInputChange}
                                        required
                                        placeholder="e.g. +1 234 567 8900"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="image">Photo (Required for AI Search)</Label>
                                <div className="flex items-center gap-2">
                                    <Input
                                        id="image"
                                        name="image"
                                        type="file"
                                        accept="image/*"
                                        onChange={handleFileChange}
                                        className="cursor-pointer"
                                        required
                                    />
                                </div>
                            </div>

                            <Button type="submit" className="w-full" disabled={isLoading}>
                                {isLoading ? "Submitting..." : "Submit Report"}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            )}

            {view === "cases" && (
                <div className="grid md:grid-cols-2 gap-4">
                    {reports.length === 0 ? (
                        <div className="col-span-2 text-center py-8 text-muted-foreground">
                            No active lost person reports.
                        </div>
                    ) : (
                        reports.map((report) => (
                            <Card key={report.id}>
                                <CardContent className="p-4">
                                    <div className="flex gap-4">
                                        <div className="h-24 w-24 bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden">
                                            {report.image_url ? (
                                                <img
                                                    src={`http://localhost:5000${report.image_url}`}
                                                    alt={report.name}
                                                    className="h-full w-full object-cover"
                                                />
                                            ) : (
                                                <User className="h-10 w-10 text-slate-400" />
                                            )}
                                        </div>
                                        <div className="flex-1 space-y-1">
                                            <div className="flex justify-between items-start">
                                                <h3 className="font-semibold text-lg">{report.name}</h3>
                                                <Badge variant={report.status === "found" ? "default" : "destructive"}>
                                                    {report.status === "found" ? "Found" : "Lost"}
                                                </Badge>
                                            </div>
                                            <p className="text-sm text-muted-foreground">Age: {report.age}</p>
                                            <p className="text-sm line-clamp-2">{report.description}</p>
                                            <div className="flex items-center gap-4 text-xs text-muted-foreground mt-2">
                                                <span className="flex items-center gap-1">
                                                    <Clock className="h-3 w-3" />
                                                    {new Date(report.reported_at).toLocaleTimeString()}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Phone className="h-3 w-3" />
                                                    {report.contact}
                                                </span>
                                            </div>
                                            {report.status === "found" && (
                                                <div className="mt-2 p-2 bg-green-50 text-green-700 text-sm rounded flex items-center gap-2">
                                                    <CheckCircle className="h-4 w-4" />
                                                    Located in {report.found_location}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </div>
            )}

            {view === "analysis" && (
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Upload Surveillance Footage</CardTitle>
                            <CardDescription>
                                Upload a video file to scan for all currently missing persons.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!videoFile ? (
                                <div className="flex items-center justify-center w-full">
                                    <label htmlFor="dropzone-file" className="flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 border-gray-300">
                                        <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                            <Upload className="w-10 h-10 mb-3 text-gray-400" />
                                            <p className="mb-2 text-sm text-gray-500"><span className="font-semibold">Click to upload</span> or drag and drop</p>
                                            <p className="text-xs text-gray-500">MP4, AVI, MOV (MAX. 100MB)</p>
                                        </div>
                                        <Input
                                            id="dropzone-file"
                                            type="file"
                                            className="hidden"
                                            accept="video/*"
                                            onChange={handleVideoSelect}
                                        />
                                    </label>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
                                        <video
                                            ref={videoRef}
                                            src={videoPreviewUrl || ""}
                                            className="w-full h-full object-contain"
                                            controls={true}
                                            playsInline
                                        />
                                        {isAnalyzing && (
                                            <div className="absolute top-4 right-4 bg-black/60 text-white px-3 py-1 rounded-full flex items-center gap-2 z-10">
                                                <Scan className="h-4 w-4 text-purple-400 animate-pulse" />
                                                <span className="text-xs font-medium animate-pulse">Scanning...</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex justify-between items-center">
                                        <div className="text-sm text-muted-foreground">
                                            File: {videoFile.name}
                                        </div>
                                        <div className="flex gap-2">
                                            <Button variant="outline" onClick={() => {
                                                setVideoFile(null)
                                                setVideoPreviewUrl(null)
                                                setAnalysisResult(null)
                                            }} disabled={isAnalyzing}>
                                                Change Video
                                            </Button>
                                            <Button
                                                onClick={startAnalysis}
                                                disabled={isAnalyzing}
                                                className="bg-purple-600 hover:bg-purple-700"
                                            >
                                                {isAnalyzing ? "Analyzing..." : "Start Analysis"}
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {analysisResult && (
                        <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <h3 className="text-xl font-semibold">Analysis Results</h3>

                            <div className="grid md:grid-cols-3 gap-4">
                                <Card>
                                    <CardContent className="p-4 text-center">
                                        <p className="text-muted-foreground">Crowd Count</p>
                                        <p className="text-2xl font-bold">{analysisResult.crowd_count}</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="p-4 text-center">
                                        <p className="text-muted-foreground">Density</p>
                                        <p className="text-2xl font-bold">{analysisResult.density_level}</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="p-4 text-center">
                                        <p className="text-muted-foreground">Sentiment</p>
                                        <p className="text-2xl font-bold">{analysisResult.sentiment}</p>
                                    </CardContent>
                                </Card>
                            </div>

                            {analysisResult.found_persons && analysisResult.found_persons.length > 0 ? (
                                <div className="space-y-4">
                                    <h4 className="font-medium flex items-center gap-2 text-green-600">
                                        <CheckCircle className="h-5 w-5" />
                                        Matches Found ({analysisResult.found_persons.length})
                                    </h4>
                                    {analysisResult.found_persons.map((match: any, idx: number) => {
                                        const report = reports.find(r => r.id === match.person_id)
                                        return (
                                            <Card key={idx} className="border-green-200 bg-green-50">
                                                <CardContent className="p-4">
                                                    <div className="flex gap-4">
                                                        <div className="h-48 w-64 bg-black rounded-lg overflow-hidden relative group cursor-pointer" onClick={() => window.open(`http://localhost:5000${match.found_frame_url}`, '_blank')}>
                                                            {match.found_frame_url ? (
                                                                <img
                                                                    src={`http://localhost:5000${match.found_frame_url}`}
                                                                    alt="Found Frame"
                                                                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                                                                />
                                                            ) : (
                                                                <div className="flex items-center justify-center h-full text-white text-xs">No Frame</div>
                                                            )}
                                                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-1 text-center">
                                                                {match.timestamp}
                                                            </div>
                                                        </div>
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex justify-between">
                                                                <h3 className="font-bold text-lg">{report?.name || "Unknown Person"}</h3>
                                                                <Badge className="bg-green-600">{match.confidence}% Match</Badge>
                                                            </div>
                                                            <p className="text-sm text-green-800">{match.description}</p>

                                                            <div className="pt-2 flex gap-2">
                                                                {match.found_frame_url && (
                                                                    <Button
                                                                        size="sm"
                                                                        className="bg-purple-600 hover:bg-purple-700 text-white"
                                                                        onClick={() => generateSaliency(match.found_frame_url)}
                                                                    >
                                                                        Generate Saliency Map (XAI)
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        )
                                    })}
                                </div>
                            ) : (
                                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
