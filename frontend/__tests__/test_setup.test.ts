test("token preset by frontend test setup before each test", () => {
  expect(localStorage.getItem("fs_token")).toBe("test-jwt");
});
