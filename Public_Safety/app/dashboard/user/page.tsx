"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle, MapPin, Users, TrendingUp, Activity, Eye, Camera, Brain, Info, Bell, Shield, MessageCircle, Search, Filter, ChevronRight, TrendingDown, AlertCircle, Video, Clock, Upload } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts"
import { AIChatbot } from "@/components/ai-chatbot"
import { AIAnomalyDetection } from "@/components/ai-anomaly-detection"
import { Navigation } from "@/components/navigation"


// Data interfaces
interface Zone {
    id: string
    name: string
    density: number
    status: string
    prediction: number
}

interface AlertItem {
    id: string | number
    type: string
    severity: string
    message: string
    time: string
    zone: string
}


export default function UserDashboard() {
    // State for dashboard data
    const [zones, setZones] = useState<Zone[]>([])
    const [alerts, setAlerts] = useState<AlertItem[]>([])
    const [crowdData, setCrowdData] = useState<any[]>([])
    const [selectedZone, setSelectedZone] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState("heatmap")
    const [saliencyMap, setSaliencyMap] = useState<string | null>(null)
    const [saliencyFrames, setSaliencyFrames] = useState<string[]>([])
    const [explanation, setExplanation] = useState<string | null>(null)
    const [processedVideo, setProcessedVideo] = useState<string | null>(null)

    // Video Upload State
    const [isUploading, setIsUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState(0)
    const [uploadStatus, setUploadStatus] = useState<string>("")
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)
    const [previewStats, setPreviewStats] = useState<string>("Initializing...")
    const [uploadFile, setUploadFile] = useState<File | null>(null)
    const [uploadZoneId, setUploadZoneId] = useState<string>("testing")
    const [detectAnomalies, setDetectAnomalies] = useState(false)
    const [uploadResult, setUploadResult] = useState<any | null>(null)

    // Load persisted analysis results on mount
    useEffect(() => {
        const saved = localStorage.getItem('photo_analysis_results')
        if (saved) {
            try {
                const data = JSON.parse(saved)
                setSaliencyFrames(data.frames || [])
                setExplanation(data.explanation || null)
                setSaliencyMap(data.saliencyMap || null)
            } catch (e) {
                console.error('Failed to load saved results:', e)
            }
        }
    }, [])

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch zones
                const resZones = await fetch('http://localhost:5000/api/realtime/all-zones')
                if (resZones.ok) {
                    const data = await resZones.json()

                    const formattedZones: Zone[] = (data.zones || []).map((z: any) => ({
                        id: z.zone_id,
                        name: z.zone_name || z.zone_id,
                        density: z.current_analysis?.density_percentage || z.current_analysis?.crowd_count || 0,
                        status: z.current_analysis?.density_level?.toLowerCase() || 'low',
                        prediction: 0
                    }))

                    if (!selectedZone && formattedZones.length > 0) {
                        setSelectedZone(formattedZones[0].id)
                    }

                    // Fetch predictions
                    for (const zone of formattedZones) {
                        try {
                            const resPred = await fetch(`http://localhost:5000/api/crowd/prediction/${zone.id}`)
                            if (resPred.ok) {
                                const predData = await resPred.json()
                                zone.prediction = predData.predicted_count_15min
                                if (predData.history && predData.history.length > 0) {
                                    zone.density = predData.history[predData.history.length - 1].density
                                }
                                // If selected zone, update chart data
                                if (zone.id === selectedZone) {
                                    // DON'T overwrite photo upload results! Check localStorage first
                                    const savedPhotoResults = localStorage.getItem('photo_analysis_results')

                                    if (!savedPhotoResults) {
                                        // Only update if NO photo upload results exist
                                        if (predData.saliency_map) setSaliencyMap(predData.saliency_map)
                                        if (predData.saliency_frames) setSaliencyFrames(predData.saliency_frames)
                                        if (predData.explanation) setExplanation(predData.explanation)
                                        if (predData.processed_video_url) setProcessedVideo(predData.processed_video_url)
                                    }

                                    const history = (predData.history || []).map((h: any) => ({
                                        time: h.time,
                                        density: h.density,
                                        prediction: null
                                    }));

                                    if (history.length > 0) {
                                        // Connect the lines by setting prediction value on the last history point
                                        const lastPoint = history[history.length - 1];
                                        lastPoint.prediction = lastPoint.density;

                                        // Add prediction point
                                        // Calculate prediction time
                                        const lastTime = history[history.length - 1].time;
                                        const [h, m] = lastTime.split(':').map(Number);
                                        const d = new Date();
                                        d.setHours(h);
                                        d.setMinutes(m + 15);
                                        const predTime = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                                        // Add prediction point
                                        history.push({
                                            time: predTime,
                                            density: null,
                                            prediction: predData.predicted_count_15min
                                        });
                                    }
                                    setCrowdData(history)
                                }
                            }
                        } catch (e) { console.error(e) }
                    }
                    setZones(formattedZones)
                }

                // Fetch alerts
                const resAlerts = await fetch('http://localhost:5000/api/anomalies/active')
                if (resAlerts.ok) {
                    const data = await resAlerts.json()
                    setAlerts(data.map((a: any) => ({
                        id: a.id,
                        type: a.type,
                        severity: a.confidence > 80 ? 'high' : 'medium',
                        message: a.description,
                        time: new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        zone: a.location
                    })))
                }
            } catch (error) {
                console.error("Error fetching dashboard data:", error)
            }
        }

        fetchData()
        const interval = setInterval(fetchData, 5000)
        return () => clearInterval(interval)
    }, [selectedZone])
    const [lostPersonForm, setLostPersonForm] = useState({
        name: "",
        description: "",
        lastSeen: "",
        contact: "",
        image: null as File | null,
    })
    const [searchResults, setSearchResults] = useState<any[]>([])
    const [isSearching, setIsSearching] = useState(false)

    const getStatusColor = (status: string) => {
        switch (status) {
            case "critical":
                return "text-destructive"
            case "high":
                return "text-orange-600"
            case "medium":
                return "text-warning"
            case "low":
                return "text-success"
            default:
                return "text-muted-foreground"
        }
    }

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "critical":
                return "destructive"
            case "high":
                return "default"  // Orange badge
            case "medium":
                return "secondary"
            case "low":
                return "outline"
            default:
                return "outline"
        }
    }

    const handleLostPersonSearch = async () => {
        if (!lostPersonForm.name || !lostPersonForm.description) return

        setIsSearching(true)
        // Mock search delay
        setTimeout(() => {
            setSearchResults([
                {
                    id: 1,
                    confidence: 92,
                    location: "Food Court - Camera 3",
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    image: "/placeholder-irf4t.png",
                },
                {
                    id: 2,
                    confidence: 78,
                    location: "Main Stage - Camera 1",
                    timestamp: new Date(Date.now() - 5 * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    image: "/person-near-stage.jpg",
                },
            ])
            setIsSearching(false)
        }, 2000)
    }

    const handleUploadFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return
        setUploadFile(file)
        setPreviewUrl(URL.createObjectURL(file))
        setUploadStatus("Ready to analyze")
        setUploadResult(null)
        setPreviewStats(`Selected: ${file.name}`)
    }

    const handleAnalyzeUpload = async () => {
        if (!uploadFile) {
            toast.error("Please select a video file first.")
            return
        }

        setIsUploading(true)
        setUploadStatus("Uploading and analyzing...")
        setUploadProgress(0)

        try {
            const formData = new FormData()
            formData.append("video", uploadFile)
            formData.append("zone_id", uploadZoneId)
            if (detectAnomalies) {
                formData.append("detect_anomalies", "true")
            }

            const res = await fetch("http://localhost:5000/api/cameras/upload-video", {
                method: "POST",
                body: formData,
            })

            const data = await res.json()
            if (!res.ok) {
                throw new Error(data.error || "Video analysis failed")
            }

            const analysis = data.analysis || {}
            setUploadResult(analysis)

            if (analysis.processed_video_url) {
                setProcessedVideo(analysis.processed_video_url)
            }
            if (analysis.saliency_map) {
                setSaliencyMap(analysis.saliency_map)
            }
            if (analysis.saliency_frames) {
                setSaliencyFrames(analysis.saliency_frames)
            }
            if (analysis.explanation) {
                setExplanation(analysis.explanation)
            }

            localStorage.setItem("photo_analysis_results", JSON.stringify({
                frames: analysis.saliency_frames || [],
                explanation: analysis.explanation || null,
                saliencyMap: analysis.saliency_map || null,
            }))

            setUploadStatus("Analysis complete")
            setUploadProgress(100)

            if (analysis.anomalies && analysis.anomalies.length > 0) {
                toast.success("Anomalies detected. Check the alerts panel.")
            } else {
                toast.success("Video analysis complete.")
            }
        } catch (error: any) {
            setUploadStatus("Analysis failed")
            toast.error(error.message || "Failed to analyze video")
        } finally {
            setIsUploading(false)
        }
    }

    return (
        <div className="min-h-screen bg-background">
            {/* Navigation Component */}
            <Navigation userRole="user" userName="John Doe" eventName="8th Mile" unreadAlerts={3} />

            <div className="container mx-auto px-4 py-6">
                <div className="grid lg:grid-cols-4 gap-6">
                    {/* Main Content */}
                    <div className="lg:col-span-3 space-y-6">
                        {/* Real-time Alerts */}
                        <div className="space-y-3">
                            {alerts.length === 0 && <p className="text-muted-foreground text-sm">No active alerts.</p>}
                            {alerts.map((alert) => (
                                <Alert key={alert.id} className={alert.severity === "high" ? "border-destructive" : ""}>
                                    <AlertTriangle className="h-4 w-4" />
                                    <AlertDescription className="flex items-center justify-between">
                                        <div>
                                            <span className="font-medium">{alert.message}</span>
                                            <span className="text-muted-foreground ml-2">• {alert.zone}</span>
                                        </div>
                                        <span className="text-sm text-muted-foreground">{alert.time}</span>
                                    </AlertDescription>
                                </Alert>
                            ))}
                        </div>

                        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                            <TabsList className="grid w-full grid-cols-4">
                                <TabsTrigger value="heatmap">Dashboard</TabsTrigger>
                                <TabsTrigger value="predictions">Predictions</TabsTrigger>
                                <TabsTrigger value="upload">Upload & Analyze</TabsTrigger>
                                <TabsTrigger value="crowd-analysis">Crowd Analysis</TabsTrigger>
                            </TabsList>


                            {/* Heat Map Tab */}
                            <TabsContent value="heatmap" className="space-y-6">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center space-x-2">
                                            <MapPin className="h-5 w-5" />
                                            <span>Real-time Crowd Heat Map</span>
                                        </CardTitle>
                                        <CardDescription>Interactive crowd density visualization by zone</CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        {/* Mock Heat Map Visualization -> Real Data */}
                                        <div className="grid grid-cols-3 gap-4 mb-6">
                                            {zones.map((zone) => (
                                                <Card
                                                    key={zone.id}
                                                    className={`cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-xl border-2 ${selectedZone === zone.id
                                                        ? "border-primary ring-4 ring-primary/10 bg-primary/5"
                                                        : "border-border/50 hover:border-primary/50 bg-card/50 backdrop-blur-sm"
                                                        }`}
                                                    onClick={() => setSelectedZone(zone.id)}
                                                >
                                                    <CardContent className="p-4">
                                                        <div className="flex items-center justify-between mb-2">
                                                            <h3 className="font-medium text-sm">{zone.name}</h3>
                                                            <Badge variant={getStatusBadge(zone.status)}>{zone.status}</Badge>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <div className="flex items-center justify-between text-sm">
                                                                <span>Current</span>
                                                                <span className={getStatusColor(zone.status)}>{zone.density}%</span>
                                                            </div>
                                                            <Progress value={zone.density} className="h-2" />
                                                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                                                <span>Predicted</span>
                                                                <span>{zone.prediction}%</span>
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>

                                        {selectedZone && (
                                            <Card className="bg-muted/30">
                                                <CardHeader>
                                                    <CardTitle className="text-lg">
                                                        {zones.find((z) => z.id === selectedZone)?.name} - Detailed View
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="grid md:grid-cols-2 gap-6">
                                                        <div>
                                                            <h4 className="font-medium mb-3">Crowd Density Trend</h4>
                                                            <ResponsiveContainer width="100%" height={200}>
                                                                <AreaChart data={crowdData}>
                                                                    <CartesianGrid strokeDasharray="3 3" />
                                                                    <XAxis dataKey="time" />
                                                                    <YAxis />
                                                                    <Tooltip />
                                                                    <Area
                                                                        type="monotone"
                                                                        dataKey="density"
                                                                        stroke="hsl(var(--primary))"
                                                                        fill="hsl(var(--primary))"
                                                                        fillOpacity={0.3}
                                                                    />
                                                                </AreaChart>
                                                            </ResponsiveContainer>
                                                        </div>
                                                        <div>
                                                            <h4 className="font-medium mb-3">Zone Statistics</h4>
                                                            <div className="space-y-3">
                                                                <div className="flex justify-between">
                                                                    <span className="text-muted-foreground">Current Capacity</span>
                                                                    <span className="font-medium">
                                                                        {zones.find((z) => z.id === selectedZone)?.density}
                                                                    </span>
                                                                </div>
                                                                <div className="flex justify-between">
                                                                    <span className="text-muted-foreground">Peak Today</span>
                                                                    <span className="font-medium">89%</span>
                                                                </div>
                                                                <div className="flex justify-between">
                                                                    <span className="text-muted-foreground">Average</span>
                                                                    <span className="font-medium">64%</span>
                                                                </div>
                                                                <div className="flex justify-between">
                                                                    <span className="text-muted-foreground">Active Cameras</span>
                                                                    <span className="font-medium">4/4</span>
                                                                </div>
                                                                <Button
                                                                    className="w-full mt-2"
                                                                    variant={saliencyMap ? "default" : "outline"}
                                                                    onClick={() => {
                                                                        if (saliencyMap) {
                                                                            const el = document.getElementById('saliency-section');
                                                                            if (el) el.scrollIntoView({ behavior: 'smooth' });
                                                                        } else {
                                                                            setActiveTab("upload");
                                                                            // Pre-select the current zone in the upload tab
                                                                            // We can't easily pass props to the tab content here without context, 
                                                                            // but the user can select it.
                                                                            alert("No analysis available for this zone. Please upload a video.");
                                                                        }
                                                                    }}
                                                                >
                                                                    <Brain className="w-4 h-4 mr-2" />
                                                                    {saliencyMap ? "View Saliency Map" : "Generate Saliency Map"}
                                                                </Button>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {saliencyMap && (
                                                        <div id="saliency-section" className="mt-6 border-t pt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                                            <h3 className="text-lg font-semibold mb-4 flex items-center">
                                                                <Brain className="w-5 h-5 mr-2 text-primary" />
                                                                AI Explainability Analysis
                                                            </h3>
                                                            <div className="grid md:grid-cols-2 gap-6">
                                                                <div className="space-y-4">
                                                                    {saliencyFrames.length > 0 ? (
                                                                        <div className="grid grid-cols-2 gap-2">
                                                                            {saliencyFrames.map((frame, idx) => (
                                                                                <div key={idx} className="relative aspect-video rounded-lg overflow-hidden border border-border bg-black/5 shadow-sm group">
                                                                                    <img src={`http://localhost:5000${frame}`} alt={`Saliency Frame ${idx + 1}`} className="object-cover w-full h-full transition-transform duration-700 group-hover:scale-105" />
                                                                                    <div className="absolute bottom-1 left-1 bg-black/70 text-white px-1.5 py-0.5 text-[10px] rounded backdrop-blur-sm">
                                                                                        Crowd Anomaly Map {idx + 1}
                                                                                    </div>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    ) : (
                                                                        <div className="relative aspect-video rounded-lg overflow-hidden border border-border bg-black/5 shadow-sm group">
                                                                            <img src={`http://localhost:5000${saliencyMap}`} alt="Saliency Map" className="object-cover w-full h-full transition-transform duration-700 group-hover:scale-105" />
                                                                            <div className="absolute bottom-2 left-2 bg-black/70 text-white px-2 py-1 text-xs rounded backdrop-blur-sm">
                                                                                Crowd Anomaly Map
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                                <div className="space-y-4">
                                                                    <div className="bg-muted/50 p-4 rounded-lg border border-border/50">
                                                                        <h4 className="font-medium mb-2 flex items-center text-sm">
                                                                            <Info className="w-4 h-4 mr-2 text-blue-500" />
                                                                            Reasoning
                                                                        </h4>
                                                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                                                            {explanation}
                                                                        </p>
                                                                    </div>
                                                                    <div className="flex items-center text-xs text-muted-foreground bg-secondary/20 p-2 rounded w-fit">
                                                                        <Shield className="w-3 h-3 mr-1" />
                                                                        Generated by YOLOv8 + DeepSORT Analysis
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        )}
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Predictions Tab */}
                            <TabsContent value="predictions" className="space-y-6">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center space-x-2">
                                            <TrendingUp className="h-5 w-5" />
                                            <span>15-Minute Crowd Predictions</span>
                                        </CardTitle>
                                        <CardDescription>AI-powered crowd flow forecasting using WE-GCN model</CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-6">
                                            <ResponsiveContainer width="100%" height={300}>
                                                <AreaChart data={crowdData}>
                                                    <defs>
                                                        <linearGradient id="colorDensity" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                                        </linearGradient>
                                                        <linearGradient id="colorPrediction" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                                    <XAxis dataKey="time" />
                                                    <YAxis />
                                                    <Tooltip
                                                        contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                                        itemStyle={{ color: 'hsl(var(--foreground))' }}
                                                    />
                                                    <Area
                                                        type="monotone"
                                                        dataKey="density"
                                                        stroke="hsl(var(--primary))"
                                                        strokeWidth={3}
                                                        fillOpacity={1}
                                                        fill="url(#colorDensity)"
                                                        name="Current Density"
                                                    />
                                                    <Area
                                                        type="monotone"
                                                        dataKey="prediction"
                                                        stroke="hsl(var(--destructive))"
                                                        strokeWidth={3}
                                                        strokeDasharray="5 5"
                                                        fillOpacity={1}
                                                        fill="url(#colorPrediction)"
                                                        name="Predicted Density"
                                                    />
                                                </AreaChart>
                                            </ResponsiveContainer>

                                            <div className="grid md:grid-cols-3 gap-4">
                                                <Card className="bg-primary/5 border-primary/20">
                                                    <CardContent className="p-4">
                                                        <div className="flex items-center space-x-2 mb-2">
                                                            <Clock className="h-4 w-4 text-primary" />
                                                            <span className="font-medium">Next 5 Minutes</span>
                                                        </div>
                                                        <p className="text-2xl font-bold text-primary">+8%</p>
                                                        <p className="text-sm text-muted-foreground">Density increase expected</p>
                                                    </CardContent>
                                                </Card>

                                                <Card className="bg-warning/5 border-warning/20">
                                                    <CardContent className="p-4">
                                                        <div className="flex items-center space-x-2 mb-2">
                                                            <AlertTriangle className="h-4 w-4 text-warning" />
                                                            <span className="font-medium">Peak Prediction</span>
                                                        </div>
                                                        <p className="text-2xl font-bold text-warning">
                                                            {crowdData.length > 0 ? crowdData[crowdData.length - 1].time : "--:--"}
                                                        </p>
                                                        <p className="text-sm text-muted-foreground">Expected peak time</p>
                                                    </CardContent>
                                                </Card>

                                                <Card className="bg-success/5 border-success/20">
                                                    <CardContent className="p-4">
                                                        <div className="flex items-center space-x-2 mb-2">
                                                            <Activity className="h-4 w-4 text-success" />
                                                            <span className="font-medium">Confidence</span>
                                                        </div>
                                                        <p className="text-2xl font-bold text-success">87%</p>
                                                        <p className="text-sm text-muted-foreground">Model accuracy</p>
                                                    </CardContent>
                                                </Card>
                                            </div>

                                            {saliencyMap && (
                                                <div className="mt-6 border-t pt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                                    <h3 className="text-lg font-semibold mb-4 flex items-center">
                                                        <Brain className="w-5 h-5 mr-2 text-primary" />
                                                        AI Explainability Analysis
                                                    </h3>
                                                    <div className="grid md:grid-cols-2 gap-6">
                                                        <div className="relative aspect-video rounded-lg overflow-hidden border border-border bg-black/5 shadow-sm group">
                                                            <img src={`http://localhost:5000${saliencyMap}`} alt="Saliency Map" className="object-cover w-full h-full transition-transform duration-700 group-hover:scale-105" />
                                                            <div className="absolute bottom-2 left-2 bg-black/70 text-white px-2 py-1 text-xs rounded backdrop-blur-sm">
                                                                Density Heatmap
                                                            </div>
                                                        </div>
                                                        <div className="space-y-4">
                                                            <div className="bg-muted/50 p-4 rounded-lg border border-border/50">
                                                                <h4 className="font-medium mb-2 flex items-center text-sm">
                                                                    <Info className="w-4 h-4 mr-2 text-blue-500" />
                                                                    Reasoning
                                                                </h4>
                                                                <p className="text-sm text-muted-foreground leading-relaxed">
                                                                    {explanation}
                                                                </p>
                                                            </div>
                                                            <div className="flex items-center text-xs text-muted-foreground bg-secondary/20 p-2 rounded w-fit">
                                                                <Shield className="w-3 h-3 mr-1" />
                                                                Generated by YOLOv8 + DeepSORT Analysis
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Upload & Analyze Tab */}
                            <TabsContent value="upload" className="space-y-6">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center space-x-2">
                                            <Upload className="h-5 w-5" />
                                            <span>Upload Video for AI Analysis</span>
                                        </CardTitle>
                                        <CardDescription>
                                            Upload a real crowd video for XAI heatmaps and optional anomaly detection.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="grid md:grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label htmlFor="video-upload">Video File</Label>
                                                <Input
                                                    id="video-upload"
                                                    type="file"
                                                    accept="video/*"
                                                    onChange={handleUploadFileChange}
                                                />
                                                <p className="text-xs text-muted-foreground">{previewStats}</p>
                                            </div>
                                            <div className="space-y-2">
                                                <Label htmlFor="zone-select">Zone</Label>
                                                <select
                                                    id="zone-select"
                                                    value={uploadZoneId}
                                                    onChange={(e) => setUploadZoneId(e.target.value)}
                                                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                                                >
                                                    <option value="food_court">Food Court</option>
                                                    <option value="parking">Parking</option>
                                                    <option value="main_stage">Main Stage</option>
                                                    <option value="testing">Testing</option>
                                                </select>
                                                <p className="text-xs text-muted-foreground">
                                                    Use <strong>Testing</strong> for fire/anomaly demos.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex items-center justify-between rounded-md border border-border/60 p-3">
                                            <div>
                                                <p className="font-medium text-sm">Run anomaly detection (Gemini)</p>
                                                <p className="text-xs text-muted-foreground">
                                                    Uses real AI analysis for fire/violence anomalies (requires GEMINI_API_KEY).
                                                </p>
                                            </div>
                                            <input
                                                type="checkbox"
                                                checked={detectAnomalies}
                                                onChange={(e) => setDetectAnomalies(e.target.checked)}
                                                className="h-4 w-4"
                                            />
                                        </div>

                                        <div className="flex items-center gap-3">
                                            <Button onClick={handleAnalyzeUpload} disabled={isUploading}>
                                                {isUploading ? "Analyzing..." : "Start Analysis"}
                                            </Button>
                                            <span className="text-sm text-muted-foreground">{uploadStatus}</span>
                                        </div>

                                        {isUploading && (
                                            <div>
                                                <Progress value={uploadProgress} className="h-2" />
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>

                                {previewUrl && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-base">Uploaded Video Preview</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <video src={previewUrl} controls className="w-full rounded-md border" />
                                        </CardContent>
                                    </Card>
                                )}

                                {processedVideo && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-base">Processed Video Output</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <video
                                                src={`http://localhost:5000${processedVideo}`}
                                                controls
                                                className="w-full rounded-md border"
                                            />
                                        </CardContent>
                                    </Card>
                                )}

                                {(saliencyMap || saliencyFrames.length > 0) && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-base">XAI Heatmaps</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            {saliencyFrames.length > 0 ? (
                                                <div className="grid grid-cols-2 gap-2">
                                                    {saliencyFrames.map((frame, idx) => (
                                                        <div key={idx} className="relative aspect-video rounded-lg overflow-hidden border bg-black/5">
                                                            <img src={`http://localhost:5000${frame}`} alt={`Saliency Frame ${idx + 1}`} className="object-cover w-full h-full" />
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="relative aspect-video rounded-lg overflow-hidden border bg-black/5">
                                                    <img src={`http://localhost:5000${saliencyMap}`} alt="Saliency Map" className="object-cover w-full h-full" />
                                                </div>
                                            )}
                                            {explanation && (
                                                <div className="mt-3 text-sm text-muted-foreground">
                                                    {explanation}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                )}

                                {uploadResult?.anomalies?.length > 0 && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-base text-destructive">Detected Anomalies</CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-3">
                                            {uploadResult.anomalies.map((anomaly: any, idx: number) => (
                                                <div key={idx} className="rounded-md border border-destructive/40 p-3">
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-medium">{anomaly.type}</span>
                                                        <Badge variant="destructive">{anomaly.confidence || "?"}%</Badge>
                                                    </div>
                                                    <p className="text-sm text-muted-foreground mt-1">{anomaly.description}</p>
                                                    {anomaly.video_timestamp && (
                                                        <p className="text-xs text-muted-foreground mt-1">Timestamp: {anomaly.video_timestamp}</p>
                                                    )}
                                                </div>
                                            ))}
                                            <Button
                                                variant="outline"
                                                onClick={() => window.open("/dashboard/responder?type=fire", "_blank")}
                                            >
                                                Open Fire Responder Dashboard
                                            </Button>
                                        </CardContent>
                                    </Card>
                                )}
                            </TabsContent>

                            {/* Crowd Analysis Tab (Replaced Video Upload) */}
                            <TabsContent value="crowd-analysis" className="space-y-6">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center space-x-2">
                                            <Video className="h-5 w-5" />
                                            <span>Live Crowd Analysis Stream</span>
                                        </CardTitle>
                                        <CardDescription>Real-time density estimation and forecasting (CSRNet + Optical Flow)</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">

                                        <div className="border rounded-lg p-4 bg-slate-50">
                                            <div className="flex justify-between items-center mb-2">
                                                <h4 className="font-medium text-sm flex items-center">
                                                    <span className="relative flex h-3 w-3 mr-2">
                                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                                    </span>
                                                    Live Analysis Running
                                                </h4>
                                                <span className="text-xs text-muted-foreground font-mono">Real-time GPU Analysis (Infinite Loop)</span>
                                            </div>
                                            <div className="relative aspect-[8/3] bg-black rounded overflow-hidden border">
                                                <img
                                                    src="http://localhost:5000/api/crowd_analysis_stream"
                                                    alt="Live Analysis Stream"
                                                    className="w-full h-full object-contain"
                                                />
                                            </div>
                                            <p className="text-xs text-center mt-2 text-muted-foreground">
                                                Processing frame-by-frame (CSRNet + Optical Flow)
                                            </p>
                                        </div>

                                        <div className="border rounded-lg p-4 bg-white mt-4 border-2 border-primary/20">
                                            <div className="flex justify-between items-center mb-4">
                                                <h4 className="font-bold text-lg flex items-center">
                                                    <Brain className="w-5 h-5 mr-2 text-purple-600" />
                                                    XAI Model Explainability Dashboard
                                                </h4>
                                                <Badge variant="outline" className="border-purple-200 bg-purple-50 text-purple-700">
                                                    Deep Analysis
                                                </Badge>
                                            </div>
                                            <p className="text-sm text-muted-foreground mb-4">
                                                Analyzing a single frame from video to reveal model decision-making process.
                                            </p>
                                            <div className="relative w-full min-h-[400px] bg-slate-100 rounded-lg overflow-hidden border flex items-center justify-center">
                                                <img
                                                    src="http://localhost:5000/api/xai/test2"
                                                    alt="XAI Dashboard"
                                                    className="w-full h-auto object-contain"
                                                    loading="lazy"
                                                />
                                            </div>
                                            <div className="mt-2 grid grid-cols-2 gap-4 text-xs text-muted-foreground">
                                                <div className="flex items-center"><Eye className="w-3 h-3 mr-1" /> Density: Predicted count heatmap</div>
                                                <div className="flex items-center"><Activity className="w-3 h-3 mr-1" /> Grad-CAM: Attention focus</div>
                                                <div className="flex items-center"><Search className="w-3 h-3 mr-1" /> Saliency: Pixel sensitivity</div>
                                                <div className="flex items-center"><TrendingUp className="w-3 h-3 mr-1" /> Int. Gradients: Feature attribution</div>
                                            </div>
                                        </div>

                                        <div className="border-t pt-4 mt-4">
                                            <h4 className="font-medium mb-2 flex items-center text-sm">
                                                <Info className="w-4 h-4 mr-2" />
                                                System Output:
                                            </h4>
                                            <ul className="text-sm text-muted-foreground space-y-1 ml-6 list-disc">
                                                <li>Left Panel: Current Crowd Density Heatmap</li>
                                                <li>Right Panel: 15-Minute Future Prediction</li>
                                                <li>Metrics: Real-time people count & density levels</li>
                                            </ul>
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>


                        </Tabs>

                        {/* AI Anomaly Detection */}
                        <AIAnomalyDetection context="user" />
                    </div>

                    {/* Sidebar */}
                    <div className="space-y-6">
                        {/* Event Info */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Event Status</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-muted-foreground">Total Attendees</span>
                                    <span className="font-medium">15,343</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-muted-foreground">Capacity</span>
                                    <span className="font-medium">20,000</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-muted-foreground">Utilization</span>
                                    <span className="font-medium text-success">76.7%</span>
                                </div>
                                <Progress value={76.7} className="h-2" />
                            </CardContent>
                        </Card>

                        {/* Quick Actions */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Quick Actions</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                <Button variant="outline" className="w-full justify-start bg-transparent">
                                    <AlertTriangle className="h-4 w-4 mr-2" />
                                    Report Incident
                                </Button>
                                <Button
                                    variant="outline"
                                    className="w-full justify-start bg-transparent"
                                    onClick={() => window.open('tel:9886744362', '_self')}
                                >
                                    <MessageCircle className="h-4 w-4 mr-2" />
                                    Contact Support
                                </Button>

                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    )
}
