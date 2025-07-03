import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import axios from "axios";
import ModelVersions from "./ModelVersions";

// Mock axios
jest.mock("axios");
const mockedAxios = axios;

describe("ModelVersions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render the component and display model versions on successful fetch", async () => {
    const mockData = {
      current: [{ id: "1", name: "Model A", version: "1.0", status: "live" }],
      candidate: [
        { id: "2", name: "Model B", version: "1.1", status: "candidate" },
      ],
    };
    mockedAxios.get.mockResolvedValueOnce({ data: mockData });

    render(<ModelVersions />);

    expect(screen.getByText("Model Versions")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Model A (v1.0) - live")).toBeInTheDocument();
      expect(
        screen.getByText("Model B (v1.1) - candidate")
      ).toBeInTheDocument();
    });
  });

  it("should display an error message if the API call fails", async () => {
    mockedAxios.get.mockRejectedValueOnce(new Error("API Error"));

    render(<ModelVersions />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch model versions.")
      ).toBeInTheDocument();
    });
  });
});
