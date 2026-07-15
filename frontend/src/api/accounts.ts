import { request } from "./client";
import type { Account, Product } from "../types/audit";

export const accountsApi = {
  list: () => request<Account[]>("/api/accounts"),
};

export const productsApi = {
  list: () => request<Product[]>("/api/products"),
};
