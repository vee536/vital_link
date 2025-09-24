import React, { useState, useEffect } from 'react';
import { Heart, Activity, Thermometer, MapPin, Clock, AlertTriangle, User } from 'lucide-react';

const VitalFrontendDashboard = () => {
  const [patientData, setPatientData] = useState({
    patientName: '',
    age: '',
    heartRate: '',
    spo2: '',
    bloodPressure: '',
    pulse: '',
    temperature: '',
    aiPrediction: '',
    gps: 'Getting location...',
    timestamp: new Date().toLocaleString(),
    alerts: []
  });

  // Auto-update timestamp every 30 seconds and get GPS on load
  useEffect(() => {
    // Get GPS location automatically on component mount
    getCurrentLocationAuto();
    
    // Update timestamp every 30 seconds
    const timestampInterval = setInterval(() => {
      setPatientData(prev => ({
        ...prev,
        timestamp: new Date().toLocaleString()
      }));
    }, 30000);

    return () => clearInterval(timestampInterval);
  }, []);

  // Auto GPS function (no user interaction needed)
  const getCurrentLocationAuto = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          setPatientData(prev => ({
            ...prev,
            gps: `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
          }));
        },
        (error) => {
          console.error('Error getting location:', error);
          setPatientData(prev => ({
            ...prev,
            gps: 'Location access denied'
          }));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000 // 5 minutes
        }
      );
    } else {
      setPatientData(prev => ({
        ...prev,
        gps: 'Geolocation not supported'
      }));
    }
  };

  const handleInputChange = (field, value) => {
    setPatientData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const addAlert = (alertMessage) => {
    setPatientData(prev => ({
      ...prev,
      alerts: [...prev.alerts, { 
        id: Date.now(), 
        message: alertMessage, 
        timestamp: new Date().toLocaleTimeString() 
      }]
    }));
  };

  const removeAlert = (alertId) => {
    setPatientData(prev => ({
      ...prev,
      alerts: prev.alerts.filter(alert => alert.id !== alertId)
    }));
  };

  const getCurrentTimestamp = () => {
    return new Date().toLocaleString();
  };

  // Manual override functions (still available if needed)
  const setCurrentLocation = () => {
    getCurrentLocationAuto();
  };

  const getVitalStatus = (vital, value) => {
    if (!value) return 'normal';
    
    const numValue = parseFloat(value);
    
    switch (vital) {
      case 'heartRate':
        return (numValue < 60 || numValue > 100) ? 'critical' : 'normal';
      case 'spo2':
        return numValue < 95 ? 'critical' : 'normal';
      case 'temperature':
        return (numValue < 36 || numValue > 37.5) ? 'critical' : 'normal';
      case 'pulse':
        return (numValue < 60 || numValue > 100) ? 'critical' : 'normal';
      default:
        return 'normal';
    }
  };

  const VitalCard = ({ icon: Icon, label, value, unit, vital }) => {
    const status = getVitalStatus(vital, value);
    const isCritical = status === 'critical';
    
    return (
      <div className={`vital-card bg-white rounded-lg shadow-md p-4 border-l-4 ${isCritical ? 'border-red-500 bg-red-50' : 'border-blue-500'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Icon className={`h-8 w-8 ${isCritical ? 'text-red-600' : 'text-blue-600'}`} />
            <div>
              <p className="text-sm font-medium text-gray-600">{label}</p>
              <p className={`text-2xl font-bold ${isCritical ? 'text-red-700' : 'text-gray-900'}`}>
                {value || '--'} {unit && value ? unit : ''}
              </p>
            </div>
          </div>
          {isCritical && (
            <AlertTriangle className="h-6 w-6 text-red-500 animate-pulse" />
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white shadow-sm rounded-lg mb-6 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center space-x-3">
                <Activity className="h-8 w-8 text-blue-600" />
                <span>Vital Frontend Dashboard</span>
              </h1>
              <p className="text-gray-600 mt-1">Real-time patient monitoring system</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Last Updated</p>
              <p className="font-medium">{patientData.timestamp}</p>
            </div>
          </div>
        </div>

        {/* Patient Information - Only Name and Age are Manual */}
        <div className="bg-white shadow-sm rounded-lg mb-6 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center space-x-2">
            <User className="h-5 w-5 text-blue-600" />
            <span>Patient Information</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Patient Name</label>
              <input
                type="text"
                value={patientData.patientName}
                onChange={(e) => handleInputChange('patientName', e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter patient name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Age</label>
              <input
                type="number"
                value={patientData.age}
                onChange={(e) => handleInputChange('age', e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter age"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">GPS Location (Auto-Updated)</label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={patientData.gps}
                  className="flex-1 p-3 border border-gray-300 rounded-md bg-gray-50"
                  placeholder="GPS coordinates"
                  readOnly
                />
                <button
                  onClick={setCurrentLocation}
                  className="px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:ring-2 focus:ring-blue-500"
                  title="Refresh location"
                >
                  <MapPin className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Timestamp (Auto-Updated)</label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={patientData.timestamp}
                  className="flex-1 p-3 border border-gray-300 rounded-md bg-gray-50"
                  placeholder="Reading timestamp"
                  readOnly
                />
                <button
                  onClick={() => handleInputChange('timestamp', getCurrentTimestamp())}
                  className="px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 focus:ring-2 focus:ring-green-500"
                  title="Manual refresh"
                >
                  <Clock className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Vital Signs - Read Only (From Vital Machine) */}
        <div className="bg-white shadow-sm rounded-lg mb-6 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center space-x-2">
            <Heart className="h-5 w-5 text-red-600" />
            <span>Vital Signs</span>
            <span className="text-sm text-gray-500 font-normal">(Live from Vital Machine)</span>
          </h2>
          
          {/* Vital Cards Display */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <VitalCard
              icon={Heart}
              label="Heart Rate"
              value={patientData.heartRate}
              unit="bpm"
              vital="heartRate"
            />
            <VitalCard
              icon={Activity}
              label="SpO2"
              value={patientData.spo2}
              unit="%"
              vital="spo2"
            />
            <VitalCard
              icon={Activity}
              label="Blood Pressure"
              value={patientData.bloodPressure}
              unit="mmHg"
              vital="bloodPressure"
            />
            <VitalCard
              icon={Thermometer}
              label="Temperature"
              value={patientData.temperature}
              unit="°C"
              vital="temperature"
            />
          </div>
          
          {/* Demo Controls (Remove these when connecting to real vital machine) */}
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800 mb-3">
              <strong>🔧 Demo Mode:</strong> Simulate vital machine data (remove when connecting real device)
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-yellow-700 mb-1">Heart Rate (bpm)</label>
                <input
                  type="number"
                  value={patientData.heartRate}
                  onChange={(e) => handleInputChange('heartRate', e.target.value)}
                  className="w-full p-2 border border-yellow-300 rounded-md focus:ring-2 focus:ring-yellow-500 text-sm"
                  placeholder="60-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-yellow-700 mb-1">SpO2 (%)</label>
                <input
                  type="number"
                  value={patientData.spo2}
                  onChange={(e) => handleInputChange('spo2', e.target.value)}
                  className="w-full p-2 border border-yellow-300 rounded-md focus:ring-2 focus:ring-yellow-500 text-sm"
                  placeholder="95-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-yellow-700 mb-1">Blood Pressure</label>
                <input
                  type="text"
                  value={patientData.bloodPressure}
                  onChange={(e) => handleInputChange('bloodPressure', e.target.value)}
                  className="w-full p-2 border border-yellow-300 rounded-md focus:ring-2 focus:ring-yellow-500 text-sm"
                  placeholder="120/80"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-yellow-700 mb-1">Temperature (°C)</label>
                <input
                  type="number"
                  step="0.1"
                  value={patientData.temperature}
                  onChange={(e) => handleInputChange('temperature', e.target.value)}
                  className="w-full p-2 border border-yellow-300 rounded-md focus:ring-2 focus:ring-yellow-500 text-sm"
                  placeholder="36.0-37.5"
                />
              </div>
            </div>
          </div>
        </div>

        {/* AI Prediction - Read Only (From AI Model) */}
        <div className="bg-white shadow-sm rounded-lg mb-6 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center space-x-2">
            <Activity className="h-5 w-5 text-purple-600" />
            <span>AI Prediction & Analysis</span>
            <span className="text-sm text-gray-500 font-normal">(From AI Model)</span>
          </h2>
          <div className="bg-gray-50 p-4 rounded-md border min-h-[100px]">
            <p className="text-gray-700 leading-relaxed">
              {patientData.aiPrediction || "🤖 Waiting for AI analysis..."}
            </p>
          </div>
          
          {/* Demo Control (Remove when connecting to real AI model) */}
          <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-md">
            <p className="text-sm text-purple-800 mb-2">
              <strong>🔧 Demo Mode:</strong> Simulate AI predictions (remove when AI model is ready)
            </p>
            <textarea
              value={patientData.aiPrediction}
              onChange={(e) => handleInputChange('aiPrediction', e.target.value)}
              className="w-full p-3 border border-purple-300 rounded-md focus:ring-2 focus:ring-purple-500 text-sm"
              placeholder="AI analysis will automatically appear here..."
              rows="3"
            />
          </div>
        </div>

        {/* Alerts Section */}
        <div className="bg-white shadow-sm rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              <span>Critical Alerts</span>
            </h2>
            <button
              onClick={() => addAlert('⚠️ Abnormal vital signs detected - Immediate attention required')}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:ring-2 focus:ring-red-500 text-sm"
            >
              Add Test Alert
            </button>
          </div>
          
          {patientData.alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p className="text-lg">No active alerts</p>
              <p className="text-sm">System monitoring normally</p>
            </div>
          ) : (
            <div className="space-y-3">
              {patientData.alerts.map(alert => (
                <div key={alert.id} className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <AlertTriangle className="h-5 w-5 text-red-600" />
                      <div>
                        <p className="text-red-800 font-medium">{alert.message}</p>
                        <p className="text-red-600 text-sm">Alert time: {alert.timestamp}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeAlert(alert.id)}
                      className="text-red-600 hover:text-red-800 font-medium text-sm px-3 py-1 border border-red-300 rounded hover:bg-red-100"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VitalFrontendDashboard;