import React from "react";
import { vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";

vi.mock("@/lib/api", () => ({ authApi: {
  requestOtp: vi.fn().mockResolvedValue(undefined),
  verify: vi.fn().mockResolvedValue({ access_token: "tok", user_id: "u1" }),
}}));

test("otp flow stores access token", async () => {
  render(<LoginPage />);
  fireEvent.change(screen.getByLabelText(/手机号/), { target: { value: "+8613800000000" } });
  fireEvent.click(screen.getByRole("button", { name: /获取验证码/ }));
  await waitFor(() => screen.getByLabelText(/验证码/));
  fireEvent.change(screen.getByLabelText(/验证码/), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: /登录/ }));
  await waitFor(() => expect(localStorage.getItem("fs_token")).toBe("tok"));
});
