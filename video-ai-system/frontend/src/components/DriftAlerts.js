import React, { useState, useEffect } from "react";
import axios from "axios";

const DriftAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState(null);
  const [retrainingStatus, setRetrainingStatus] = useState("");

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const response = await axios.get("/api/governance/drift_alerts");
        setAlerts(response.data);
      } catch (err) {
        setError("Failed to fetch drift alerts.");
        console.error(err);
      }
    };
    fetchAlerts();
  }, []);

  const handleRetrain = async () => {
    setRetrainingStatus("Retraining initiated...");
    try {
      await axios.post("/api/governance/retrain");
      setRetrainingStatus("Retraining job started successfully.");
    } catch (err) {
      setRetrainingStatus("Failed to start retraining job.");
      console.error(err);
    }
  };

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="drift-alerts">
      <h2>Drift Alerts</h2>
      <button onClick={handleRetrain}>Trigger Retraining</button>
      {retrainingStatus && <p>{retrainingStatus}</p>}
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Drift Score</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td>
                {alert.model_name} (v{alert.model_version})
              </td>
              <td>{alert.drift_score.toFixed(4)}</td>
              <td>{new Date(alert.timestamp).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DriftAlerts;
