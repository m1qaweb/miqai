import React, { useState } from "react";
import axios from "axios";

const ApprovalControls = ({ modelId }) => {
  const [status, setStatus] = useState("");

  const handleApproval = async (decision) => {
    setStatus(`Submitting ${decision}...`);
    try {
      await axios.post("/api/governance/approve", {
        model_id: modelId,
        decision,
      });
      setStatus(`Model ${decision}d successfully.`);
    } catch (err) {
      setStatus(`Failed to submit ${decision}.`);
      console.error(err);
    }
  };

  return (
    <div className="approval-controls">
      <h3>Approval Controls</h3>
      <p>Model ID: {modelId}</p>
      <button onClick={() => handleApproval("approve")}>Approve</button>
      <button onClick={() => handleApproval("reject")}>Reject</button>
      {status && <p>{status}</p>}
    </div>
  );
};

export default ApprovalControls;
