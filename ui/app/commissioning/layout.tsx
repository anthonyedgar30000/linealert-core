import Link from "next/link";
import type { ReactNode } from "react";

import styles from "./commissioning-layout.module.css";

export default function CommissioningLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <div className={styles.ribbon} role="status">
        <div>
          <span>COMMISSIONING FAULT-INJECTION LAB</span>
          <b>Synthetic fixtures are controlled test inputs · not operator diagnoses</b>
        </div>
        <Link href="/">← Operator View</Link>
      </div>
      {children}
    </>
  );
}
