import "@testing-library/jest-dom/vitest";
import { vi, beforeEach } from "vitest";

const _store: Record<string, string> = {};
const fakeLocalStorage = {
  getItem: (key: string) => _store[key] ?? null,
  setItem: (key: string, value: string) => { _store[key] = value; },
  removeItem: (key: string) => { delete _store[key]; },
  clear: () => { Object.keys(_store).forEach(k => delete _store[k]); },
  key: (i: number) => Object.keys(_store)[i] ?? null,
  get length() { return Object.keys(_store).length; },
};
vi.stubGlobal("localStorage", fakeLocalStorage);

beforeEach(() => {
  fakeLocalStorage.clear();
  fakeLocalStorage.setItem("fs_token", "test-jwt");
  fakeLocalStorage.setItem("fs_user_id", "u_test");
});
