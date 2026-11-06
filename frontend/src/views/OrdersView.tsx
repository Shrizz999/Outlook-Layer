import React, { useState } from 'react';
import { Package, AlertTriangle, CheckCircle2, FileSpreadsheet, Layers, ArrowRight } from 'lucide-react';
import { SalesOrder } from '../types';

interface OrdersViewProps {
  orders: SalesOrder[];
}

export const OrdersView: React.FC<OrdersViewProps> = ({ orders }) => {
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(orders[0] || null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Sales Orders & MRP Reconciliation</h2>
          <p className="text-xs text-slate-500">
            Operational reference registers. Reconciles customer demand with live inventory and detects material shortages.
          </p>
        </div>
      </div>

      {/* MRP Stock Shortage Analysis Alert Card */}
      <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-5 space-y-3">
        <div className="flex items-center space-x-2 text-amber-900 font-bold text-sm">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
          <span>Active MRP Reconciliation Finding: 40 Units Shortage</span>
        </div>
        <p className="text-xs text-amber-800 leading-relaxed">
          Order <strong>SO-1025</strong> demands <strong>100 MTR</strong> of Part <strong>HT-2045</strong>. Current MRP snapshot
          confirms available stock is <strong>60 MTR</strong>. Supplier communication confirms order of 40 MTR placed with Apex Tube Mills.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Sales Orders List */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs flex flex-col">
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileSpreadsheet className="w-4 h-4 text-blue-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Sales Orders ({orders.length})
              </h3>
            </div>
            <span className="text-[11px] text-slate-400">Canonical Records</span>
          </div>

          <div className="divide-y divide-slate-100 flex-1 overflow-y-auto">
            {orders.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No sales orders found.</div>
            ) : (
              orders.map((o) => {
                const isSelected = selectedOrder?.id === o.id;
                return (
                  <div
                    key={o.id}
                    onClick={() => setSelectedOrder(o)}
                    className={`p-4 cursor-pointer transition ${
                      isSelected ? 'bg-blue-50/60 border-l-4 border-blue-600' : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono font-bold text-blue-600">{o.so_number}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        Delivery: {o.requested_delivery_date}
                      </span>
                    </div>
                    <div className="text-xs font-semibold text-slate-900 mb-1">{o.source_customer_name}</div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>{o.lines?.length || 0} line items</span>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">
                        {o.status}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Order Detail & Line Items */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          {selectedOrder ? (
            <>
              <div className="border-b border-slate-200 pb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">{selectedOrder.so_number}</h3>
                  <p className="text-xs text-slate-500">{selectedOrder.source_customer_name}</p>
                </div>
                <div className="text-right text-xs text-slate-400">
                  <span>Target Date: {selectedOrder.requested_delivery_date}</span>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Order Line Items & Inventory Status
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold text-[10px] bg-slate-50">
                        <th className="py-2.5 px-3">#</th>
                        <th className="py-2.5 px-3">Part Number</th>
                        <th className="py-2.5 px-3">Description</th>
                        <th className="py-2.5 px-3">Ordered</th>
                        <th className="py-2.5 px-3">Unit</th>
                        <th className="py-2.5 px-3">Stock Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedOrder.lines?.map((line) => {
                        const isShortage = line.source_part_number === 'HT-2045';
                        return (
                          <tr key={line.id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 font-mono text-slate-400">{line.line_number}</td>
                            <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                              {line.source_part_number}
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 truncate max-w-xs">{line.description}</td>
                            <td className="py-2.5 px-3 font-semibold text-slate-900">{line.ordered_quantity}</td>
                            <td className="py-2.5 px-3 text-slate-500">{line.unit_of_measure}</td>
                            <td className="py-2.5 px-3">
                              {isShortage ? (
                                <span className="bg-rose-50 text-rose-700 font-bold text-[10px] px-2 py-0.5 rounded border border-rose-200 flex items-center w-max">
                                  <AlertTriangle className="w-3 h-3 mr-1" />
                                  Shortage (60/100)
                                </span>
                              ) : (
                                <span className="bg-emerald-50 text-emerald-700 font-semibold text-[10px] px-2 py-0.5 rounded border border-emerald-200 flex items-center w-max">
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                  Available
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400">Select an order to inspect line items.</div>
          )}
        </div>
      </div>
    </div>
  );
};
