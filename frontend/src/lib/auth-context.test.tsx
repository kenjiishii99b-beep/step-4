import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { apiClient } from "@/lib/api-client";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { setSession } from "@/lib/token-store";
import { StaffSession } from "@/types/auth";

jest.mock("@/lib/api-client", () => ({
  apiClient: { post: jest.fn() },
}));

const mockedPost = apiClient.post as jest.Mock;

const SESSION: StaffSession = {
  access_token: "test-access-token",
  token_type: "bearer",
  staff_id: "S001",
  staff_name: "テスト太郎",
  role: "STAFF",
};

function TestConsumer() {
  const { session, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="access-token">{session?.access_token ?? "none"}</span>
      <button onClick={() => login("S001", "password")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    // モジュールスコープのセッション状態を各テスト間でリセットする。
    setSession(null);
    mockedPost.mockReset();
    // マウント時の refreshSession（BFF Cookie 再認証）は失敗させ、ログインテストに影響させない。
    global.fetch = jest.fn().mockResolvedValue({ ok: false });
  });

  // FE-U09: Access Tokenの保持（セキュリティ）— ログイン成功時、メモリ状態で保持される
  test("ログイン成功時、Access Tokenがメモリ上のセッション状態として保持される", async () => {
    mockedPost.mockResolvedValueOnce({ data: SESSION });
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId("access-token")).toHaveTextContent("none");

    await user.click(screen.getByText("login"));

    await waitFor(() => {
      expect(screen.getByTestId("access-token")).toHaveTextContent("test-access-token");
    });
    expect(mockedPost).toHaveBeenCalledWith("/auth/login", {
      staff_id: "S001",
      password: "password",
    });
  });

  // FE-U09: localStorage等の永続ストレージへは保存しないこと
  test("ログイン成功時、localStorageへはAccess Tokenを保存しない", async () => {
    mockedPost.mockResolvedValueOnce({ data: SESSION });
    const setItemSpy = jest.spyOn(Storage.prototype, "setItem");
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await user.click(screen.getByText("login"));

    await waitFor(() => {
      expect(screen.getByTestId("access-token")).toHaveTextContent("test-access-token");
    });
    expect(setItemSpy).not.toHaveBeenCalled();
    expect(localStorage.getItem("access_token")).toBeNull();

    setItemSpy.mockRestore();
  });

  test("ログアウト時、メモリ上のセッション状態が破棄される", async () => {
    mockedPost.mockResolvedValueOnce({ data: SESSION });
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await user.click(screen.getByText("login"));
    await waitFor(() => {
      expect(screen.getByTestId("access-token")).toHaveTextContent("test-access-token");
    });

    await user.click(screen.getByText("logout"));

    await waitFor(() => {
      expect(screen.getByTestId("access-token")).toHaveTextContent("none");
    });
  });
});
