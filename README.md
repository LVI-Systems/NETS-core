# NETS-Core 
**Unified event trading architecture that respects traders**

# Introduction
Current event contract markets operate on trading architectures that significantly lag behind those of other financial derivatives. This leads to two main issues: **liquidity fragmentation** and **capital inefficancy**:  

- Liquidity in mutually-exclusive event contracts are **siloed into individual order books**, leading to **inefficient execution and value extraction by arbitrage**. Liquidity which should be mathematically linked are fragmented, which means that a fraction of true market liquidity is available to any aggressing order. This reuslts in heightened slippage for large marketable orders, especially in volatile market conditions.
- Collateralization of positions are **managed manually with YES and NO contracts**, where it is possible to **simultaneously hold YES and NO contracts without collateral relief or netting**. Manual adjustment of orders to avoid this scenario would lead to **frequent loss of queue position** and **significant processing load**. This significantly impacts scalping or market-making strategies.

This design leads major event contract venues to function primarily as **predatory liquidity harvesting mechanisms**, going agains the spirit of **fair price discovery, information aggregation and efficient expression of diverse convictions and strategies**.  

**NETS-Core is designed to address all above issues.**
