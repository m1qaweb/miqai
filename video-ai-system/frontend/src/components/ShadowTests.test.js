import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import axios from "axios";
import ShadowTests from "./ShadowTests";

// Mock axios
jest.mock("axios");
const mockedAxios = axios;

describe("ShadowTests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render the component and display shadow test results on successful fetch", async () => {
    const mockData = [
      {
        id: "1",
        model_a_name: "Model A",
        model_a_version: "1.0",
        model_b_name: "Model B",
        model_b_version: "1.1",
        result: "Mismatch",
        passed: false,
      },
      {
        id: "2",
        model_a_name: "Model A",
        model_a_version: "1.0",
        model_b_name: "Model C",
        model_b_version: "1.2",
        result: "Match",
        passed: true,
      },
    ];
    mockedAxios.get.mockResolvedValueOnce({ data: mockData });

    render(<ShadowTests />);

    expect(screen.getByText("Shadow Test Results")).toBeInTheDocument();

    await screen.findByText("Model B (v1.1)"); // Wait for one element to appear

    expect(screen.getAllByText("Model A (v1.0)")).toHaveLength(2);
    expect(screen.getByText("Model B (v1.1)")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.getByText("Model C (v1.2)")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("should display an error message if the API call fails", async () => {
    mockedAxios.get.mockRejectedValueOnce(new Error("API Error"));

    render(<ShadowTests />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch shadow test results.")
      ).toBeInTheDocument();
    });
  });
});
