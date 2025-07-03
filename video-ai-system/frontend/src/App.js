import React from "react";
import "./App.css";
import ModelVersions from "./components/ModelVersions";
import ShadowTests from "./components/ShadowTests";
import DriftAlerts from "./components/DriftAlerts";
import ApprovalControls from "./components/ApprovalControls";

function App() {
  // A placeholder model ID for the ApprovalControls component
  const candidateModelId = "candidate-model-123";

  return (
    <div className="App">
      <header className="App-header">
        <h1>Governance Dashboard</h1>
      </header>
      <main>
        <div className="dashboard-container">
          <div className="dashboard-section">
            <ModelVersions />
          </div>
          <div className="dashboard-section">
            <ShadowTests />
          </div>
          <div className="dashboard-section">
            <DriftAlerts />
          </div>
          <div className="dashboard-section">
            <ApprovalControls modelId={candidateModelId} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
