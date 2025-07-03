import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import axios from "axios";
import ApprovalControls from "./ApprovalControls";

const mockedAxios = axios;

describe("ApprovalControls", () => {
  const modelId = "test-model-123";

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render the component with the correct model ID", () => {
    render(<ApprovalControls modelId={modelId} />);
    expect(screen.getByText(`Model ID: ${modelId}`)).toBeInTheDocument();
  });

  it('should call the approve API when the "Approve" button is clicked', async () => {
    mockedAxios.post.mockResolvedValueOnce({});
    render(<ApprovalControls modelId={modelId} />);

    fireEvent.click(screen.getByText("Approve"));

    expect(screen.getByText("Submitting approve...")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/governance/approve", {
        model_id: modelId,
        decision: "approve",
      });
    });

    expect(
      await screen.findByText("Model approved successfully.")
    ).toBeInTheDocument();
  });

  it('should call the reject API when the "Reject" button is clicked', async () => {
    mockedAxios.post.mockResolvedValueOnce({});
    render(<ApprovalControls modelId={modelId} />);

    fireEvent.click(screen.getByText("Reject"));

    expect(screen.getByText("Submitting reject...")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/governance/approve", {
        model_id: modelId,
        decision: "reject",
      });
    });

    expect(
      await screen.findByText("Model rejectd successfully.")
    ).toBeInTheDocument();
  });

  it("should display an error message if the API call fails", async () => {
    mockedAxios.post.mockRejectedValueOnce(new Error("API Error"));
    render(<ApprovalControls modelId={modelId} />);

    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(screen.getByText("Failed to submit approve.")).toBeInTheDocument();
    });
  });
});
