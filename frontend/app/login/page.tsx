"use client";
import React, { useState } from "react";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);

  const ask = async () => {
    await authApi.requestOtp(phone);
    setSent(true);
  };

  const submit = async () => {
    const { access_token } = await authApi.verify(phone, code);
    localStorage.setItem("fs_token", access_token);
  };

  return (
    <form onSubmit={(e) => e.preventDefault()}>
      <label>
        手机号
        <input value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      <button type="button" onClick={ask}>获取验证码</button>
      {sent && (
        <>
          <label>
            验证码
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
          <button type="button" onClick={submit}>登录</button>
        </>
      )}
    </form>
  );
}
