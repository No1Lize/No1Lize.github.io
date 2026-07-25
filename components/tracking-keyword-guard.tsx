"use client";

import { useEffect, useState } from "react";
import { validateStrictPersonLabel } from "@/lib/strict-person-label";
import { validateTrackingKeyword } from "@/lib/user-tracking";

type GuardState = {
  visible: boolean;
  message: string;
  kind: "success" | "warning" | "error";
  top: number;
  left: number;
  width: number;
};

t