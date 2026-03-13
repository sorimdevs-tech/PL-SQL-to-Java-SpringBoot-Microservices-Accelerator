import { ArrowRight, FileDown } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { TransactionItem } from "@/types/dashboard"

interface TransactionTableProps {
  transactions: TransactionItem[]
}

function statusVariant(status: TransactionItem["status"]) {
  switch (status) {
    case "Approved":
      return "success"
    case "Pending":
      return "warning"
    default:
      return "danger"
  }
}

export function TransactionTable({ transactions }: TransactionTableProps) {
  return (
    <Card className="animate-rise delay-3">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>Payments & Approvals</CardTitle>
            <CardDescription>Recent high-value transactions requiring visibility</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <FileDown className="h-4 w-4" />
              Download CSV
            </Button>
            <Button size="sm">
              View all
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="overflow-x-auto">
          <table className="min-w-full table-auto border-collapse text-sm">
            <thead>
              <tr className="border-y border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-3 pr-4">Transaction</th>
                <th className="py-3 pr-4">Vendor</th>
                <th className="py-3 pr-4">Category</th>
                <th className="py-3 pr-4">Amount</th>
                <th className="py-3 pr-4">Due Date</th>
                <th className="py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((item) => (
                <tr key={item.id} className="border-b border-slate-100 text-slate-700 hover:bg-slate-50/70">
                  <td className="py-3 pr-4 font-semibold text-slate-900">{item.id}</td>
                  <td className="py-3 pr-4">{item.vendor}</td>
                  <td className="py-3 pr-4">{item.category}</td>
                  <td className="py-3 pr-4 font-semibold">{item.amount}</td>
                  <td className="py-3 pr-4">{item.dueDate}</td>
                  <td className="py-3">
                    <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
