import React, { useState, useEffect } from "react";
import axios from "axios";

const ShadowTests = () => {
  const [testResults, setTestResults] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTestResults = async () => {
      try {
        const response = await axios.get("/api/governance/shadow_tests");
        setTestResults(response.data);
      } catch (err) {
        setError("Failed to fetch shadow test results.");
        console.error(err);
      }
    };
    fetchTestResults();
  }, []);

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="shadow-tests">
      <h2>Shadow Test Results</h2>
      <table>
        <thead>
          <tr>
            <th>Model A</th>
            <th>Model B</th>
            <th>Result</th>
            <th>Passed</th>
          </tr>
        </thead>
        <tbody>
          {testResults.map((result) => (
            <tr key={result.id}>
              <td>
                {result.model_a_name} (v{result.model_a_version})
              </td>
              <td>
                {result.model_b_name} (v{result.model_b_version})
              </td>
              <td>{result.result}</td>
              <td>{result.passed ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ShadowTests;
