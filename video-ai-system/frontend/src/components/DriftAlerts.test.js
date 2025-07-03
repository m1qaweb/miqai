import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import axios from "axios";
import DriftAlerts from "./DriftAlerts";

// Mock axios
jest.mock("axios");
const mockedAxios = axios;

describe("DriftAlerts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render the component and display drift alerts on successful fetch", async () => {
    const mockData = [
      {
        id: "1",
        model_name: "Model A",
        model_version: "1.0",
        drift_score: 0.75,
        timestamp: "2023-10-27T10:00:00Z",
      },
    ];
    mockedAxios.get.mockResolvedValueOnce({ data: mockData });

    render(<DriftAlerts />);

    expect(screen.getByText("Drift Alerts")).toBeInTheDocument();

    expect(await screen.findByText("Model A (v1.0)")).toBeInTheDocument();
    expect(await screen.findByText("0.7500")).toBeInTheDocument();
  });

  it("should display an error message if the API call fails", async () => {
    mockedAxios.get.mockRejectedValueOnce(new Error("API Error"));

    render(<DriftAlerts />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch drift alerts.")
      ).toBeInTheDocument();
    });
  });

  it("should call the retraining API when the button is clicked", async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: [] }); // Initial load
    mockedAxios.post.mockResolvedValueOnce({
      data: { message: "Retraining started" },
    });

    render(<DriftAlerts />);

    fireEvent.click(screen.getByText("Trigger Retraining"));

    expect(screen.getByText("Retraining initiated...")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/governance/retrain");
    });
    expect(
      await screen.findByText("Retraining job started successfully.")
    ).toBeInTheDocument();
  });

  it("should display an error message if the retraining API call fails", async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: [] }); // Initial load
    mockedAxios.post.mockRejectedValueOnce(new Error("API Error"));

    render(<DriftAlerts />);

    fireEvent.click(screen.getByText("Trigger Retraining"));

    expect(screen.getByText("Retraining initiated...")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/governance/retrain");
    });

    expect(
      await screen.findByText("Failed to start retraining job.")
    ).toBeInTheDocument();
  });
});
