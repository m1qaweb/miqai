import React, { useState, useEffect } from "react";
import axios from "axios";

const ModelVersions = () => {
  const [models, setModels] = useState({ current: [], candidate: [] });
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await axios.get("/api/governance/models");
        setModels(response.data);
      } catch (err) {
        setError("Failed to fetch model versions.");
        console.error(err);
      }
    };
    fetchModels();
  }, []);

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="model-versions">
      <h2>Model Versions</h2>
      <div className="model-list">
        <h3>Current Models</h3>
        <ul>
          {models.current.map((model) => (
            <li key={model.id}>
              {model.name} (v{model.version}) - {model.status}
            </li>
          ))}
        </ul>
      </div>
      <div className="model-list">
        <h3>Candidate Models</h3>
        <ul>
          {models.candidate.map((model) => (
            <li key={model.id}>
              {model.name} (v{model.version}) - {model.status}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default ModelVersions;
