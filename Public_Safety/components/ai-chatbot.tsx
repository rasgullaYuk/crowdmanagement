"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { MessageCircle, Send, Bot, User, X, Minimize2, Maximize2 } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

interface AIChatbotProps {
  context?: "user" | "responder" | "admin"
}

export function AIChatbot({ context = "user" }: AIChatbotProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: `Hello! I'm CrowdGuard AI, your intelligent event management assistant. I can help you with crowd information, safety updates, incident reports, and answer questions about the event. How can I assist you today?`,
      timestamp: new Date(),
    },
  ])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const contextPrompts = {
    user: [
      "What's the current crowd density at Main Stage?",
      "Show me 15-minute predictions",
      "Help me find a lost person",
      "What are the predicted busy times?",
    ],
    responder: [
      "Show me active incidents in my zone",
      "What's the 15-minute crowd forecast?",
      "What's the fastest route to Food Court?",
      "Request backup for current incident",
    ],
    admin: [
      "Generate system health report",
      "Show me 15-minute zone predictions",
      "What are the current bottlenecks?",
      "Optimize responder deployment",
    ],
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsLoading(true)

    // Mock AI response - in real app, this would call your AI service
    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: generateMockResponse(inputValue, context),
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, aiResponse])
      setIsLoading(false)
    }, 1500)
  }

  const generateMockResponse = (input: string, context: string): string => {
    const lowerInput = input.toLowerCase()

    if (lowerInput.includes("crowd") || lowerInput.includes("density")) {
      if (lowerInput.includes("15") || lowerInput.includes("prediction") || lowerInput.includes("forecast")) {
        return "15-Minute Crowd Density Predictions:\n\nMain Stage: 85% → 92% (+7% increase)\nFood Court: 72% → 78% (+6% increase)\nVIP Area: 45% → 38% (-7% decrease)\n\nRecommendation: Avoid Main Stage for next 20 minutes. VIP Area is getting less crowded - perfect time to visit!"
      }
      return "Current crowd density at Main Stage is 85% (high). Food Court is at 72% (medium). I recommend avoiding Main Stage area for the next 15 minutes. Would you like me to suggest alternative routes?"
    }

    if (lowerInput.includes("lost") || lowerInput.includes("find")) {
      return "I can help you search for a lost person using our AI-powered CCTV analysis. Please provide a description and photo if available. Our system will scan all camera feeds and provide potential matches with location timestamps."
    }

    if (lowerInput.includes("incident") || lowerInput.includes("emergency")) {
      if (context === "responder") {
        return "You have 2 active incidents in your assigned zones: MED-001 at Main Stage (high priority) and MED-002 at Food Court (medium priority). MED-001 requires immediate attention - person collapsed, unconscious. ETA to location: 3 minutes."
      }
      return "I can help you report an incident. Please describe what you've observed, and I'll categorize it and alert the appropriate responders. For immediate emergencies, please call 911."
    }

    if (lowerInput.includes("prediction") || lowerInput.includes("forecast") || lowerInput.includes("15-minute") || lowerInput.includes("15 minute")) {
      if (context === "admin") {
        return "15-Minute AI Predictions:\n\nCRITICAL RISK:\n• Main Stage: 92% → 98% (+6% increase)\n• Food Court: 78% → 85% (+7% increase)\n\nHIGH RISK:\n• Entrance A: 65% → 72% (+7% increase)\n• Parking: 58% → 65% (+7% increase)\n\nIMPROVING:\n• VIP Area: 45% → 38% (-7% decrease)\n• Backstage: 35% → 42% (+7% increase)\n\nRecommendations:\n• Deploy crowd control at Main Stage\n• Add security at Food Court\n• Consider VIP Area as overflow zone"
      } else if (context === "responder") {
        return "15-Minute Crowd Forecast for Your Zone:\n\nMain Stage (Your Area):\n• Current: 92% density\n• Predicted: 98% density (+6%)\n• Risk Level: CRITICAL\n\nAction Required:\n• Prepare for crowd surge\n• Request additional backup\n• Set up crowd control barriers\n• Monitor for potential incidents\n\nTimeline: Critical density expected in 12-15 minutes"
      } else {
        return "15-Minute Crowd Predictions:\n\nAreas to AVOID:\n• Main Stage: Will reach 98% capacity\n• Food Court: Expecting 85% density\n\nSAFER Areas:\n• VIP Area: Decreasing to 38%\n• Backstage: Low density (42%)\n\nSmart Tips:\n• Visit Main Stage now or wait 30+ minutes\n• Food Court will be busy - consider alternatives\n• VIP Area is getting less crowded"
      }
    }

    if (lowerInput.includes("route") || lowerInput.includes("navigate")) {
      return "Fastest route to your destination: Take the service path behind VIP area (2.3 minutes). Alternative route via main walkway is currently congested (4.8 minutes). I'll send turn-by-turn directions to your device."
    }

    if (lowerInput.includes("analytics") || lowerInput.includes("report")) {
      return "System Health Report: 98.5% uptime, 24/24 cameras online, AI prediction accuracy at 87%. Today's metrics: 30 incidents resolved, 4.2 min avg response time. Zone utilization: Main Stage (critical), Food Court (high), others (normal)."
    }

    // Default response
    return "I understand you're asking about event management. I can help with crowd monitoring, 15-minute predictions, incident reporting, lost person searches, navigation, and system analytics. Could you be more specific about what you need assistance with?"
  }

  const handleQuickPrompt = (prompt: string) => {
    setInputValue(prompt)
  }

  if (!isOpen) {
    return (
      <Button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-lg pulse-glow"
        size="lg"
      >
        <MessageCircle className="h-6 w-6" />
      </Button>
    )
  }

  return (
    <Card className={`fixed bottom-6 right-6 w-96 shadow-xl z-50 ${isMinimized ? "h-16" : "h-[500px]"}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">CrowdGuard AI</CardTitle>
            <Badge variant="outline" className="bg-success/10 text-success border-success/20">
              Online
            </Badge>
          </div>
          <div className="flex items-center space-x-1">
            <Button variant="ghost" size="sm" onClick={() => setIsMinimized(!isMinimized)}>
              {isMinimized ? <Maximize2 className="h-4 w-4" /> : <Minimize2 className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      {!isMinimized && (
        <CardContent className="flex flex-col h-[400px]">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  <div className="flex items-start space-x-2">
                    {message.role === "assistant" && <Bot className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                    {message.role === "user" && <User className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                    <div className="text-sm whitespace-pre-line">{message.content}</div>
                  </div>
                  <div className="text-xs opacity-70 mt-1">
                    {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted text-muted-foreground rounded-lg p-3 max-w-[80%]">
                  <div className="flex items-center space-x-2">
                    <Bot className="h-4 w-4" />
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-current rounded-full animate-bounce"></div>
                      <div
                        className="w-2 h-2 bg-current rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-current rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Quick Prompts */}
          <div className="mb-3">
            <div className="flex flex-wrap gap-1">
              {contextPrompts[context].slice(0, 2).map((prompt, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  className="text-xs h-7 bg-transparent"
                  onClick={() => handleQuickPrompt(prompt)}
                >
                  {prompt}
                </Button>
              ))}
            </div>
          </div>

          {/* Input */}
          <div className="flex space-x-2">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask me anything about the event..."
              onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
              disabled={isLoading}
            />
            <Button onClick={handleSendMessage} disabled={isLoading || !inputValue.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
