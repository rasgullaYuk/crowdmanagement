"use client"

import { useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Shield, Bell, Settings, LogOut, Menu, X } from "lucide-react"

interface NavigationProps {
  userRole?: "user" | "admin" | "responder"
  userName?: string
  eventName?: string
  unreadAlerts?: number
}

export function Navigation({
  userRole,
  userName = "John Doe",
  eventName = "Summer Music Festival",
  unreadAlerts = 3,
}: NavigationProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const getDashboardLink = () => {
    switch (userRole) {
      case "admin":
        return "/dashboard/admin"
      case "responder":
        return "/dashboard/responder"
      case "user":
        return "/dashboard/user"
      default:
        return "/"
    }
  }

  const getRoleColor = () => {
    switch (userRole) {
      case "admin":
        return "bg-purple-100 text-purple-800"
      case "responder":
        return "bg-red-100 text-red-800"
      case "user":
        return "bg-blue-100 text-blue-800"
      default:
        return "bg-gray-100 text-gray-800"
    }
  }

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Brand */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">CrowdGuard</span>
            </Link>
            {eventName && (
              <div className="hidden md:block ml-4 pl-4 border-l border-gray-300">
                <span className="text-sm text-gray-600">{eventName}</span>
              </div>
            )}
          </div>

          {/* Desktop Navigation */}
          {userRole && (
            <div className="hidden md:flex items-center space-x-4">
              <Link href={getDashboardLink()}>
                <Button variant="ghost" size="sm">
                  Dashboard
                </Button>
              </Link>

              {/* Alerts */}
              <Button variant="ghost" size="sm" className="relative">
                <Bell className="h-4 w-4" />
                {unreadAlerts > 0 && (
                  <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
                    {unreadAlerts}
                  </Badge>
                )}
              </Button>

              {/* User Info */}
              <div className="flex items-center space-x-2">
                <Badge className={getRoleColor()}>{userRole.charAt(0).toUpperCase() + userRole.slice(1)}</Badge>
                <span className="text-sm text-gray-700">{userName}</span>
              </div>

              {/* Settings */}
              <Button variant="ghost" size="sm">
                <Settings className="h-4 w-4" />
              </Button>

              {/* Logout */}
              <Button variant="ghost" size="sm">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Auth Buttons for Non-logged in Users */}
          {!userRole && (
            <div className="hidden md:flex items-center space-x-2">
              <Link href="/auth/login">
                <Button variant="ghost">Login</Button>
              </Link>
              <Link href="/auth/register">
                <Button>Register Event</Button>
              </Link>
            </div>
          )}

          {/* Mobile Menu Button */}
          <div className="md:hidden">
            <Button variant="ghost" size="sm" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
              {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 py-4">
            {userRole ? (
              <div className="space-y-2">
                <div className="px-4 py-2">
                  <div className="flex items-center space-x-2">
                    <Badge className={getRoleColor()}>{userRole.charAt(0).toUpperCase() + userRole.slice(1)}</Badge>
                    <span className="text-sm text-gray-700">{userName}</span>
                  </div>
                  {eventName && <div className="text-sm text-gray-600 mt-1">{eventName}</div>}
                </div>
                <Link href={getDashboardLink()}>
                  <Button variant="ghost" className="w-full justify-start">
                    Dashboard
                  </Button>
                </Link>
                <Button variant="ghost" className="w-full justify-start">
                  <Bell className="h-4 w-4 mr-2" />
                  Alerts
                  {unreadAlerts > 0 && <Badge className="ml-auto">{unreadAlerts}</Badge>}
                </Button>
                <Button variant="ghost" className="w-full justify-start">
                  <Settings className="h-4 w-4 mr-2" />
                  Settings
                </Button>
                <Button variant="ghost" className="w-full justify-start">
                  <LogOut className="h-4 w-4 mr-2" />
                  Logout
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                <Link href="/auth/login">
                  <Button variant="ghost" className="w-full">
                    Login
                  </Button>
                </Link>
                <Link href="/auth/register">
                  <Button className="w-full">Register Event</Button>
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}
