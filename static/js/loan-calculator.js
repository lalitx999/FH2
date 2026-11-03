// คำนวณในเบราว์เซอร์เท่านั้น ตัวเลขรายได้และหนี้ไม่ถูกส่งออกจากเครื่องผู้ใช้
(() => {
  const baht = (value) => `฿${Math.round(value).toLocaleString("th-TH")}`;

  function monthlyPayment(principal, annualRate, years) {
    const months = years * 12;
    const rate = annualRate / 100 / 12;
    return rate === 0 ? principal / months : (principal * rate) / (1 - (1 + rate) ** -months);
  }

  function isValid({ price, down, rate, years }) {
    return price > 0 && down >= 0 && down < 100 && rate >= 0 && years > 0;
  }

  function init(root) {
    const input = (name) => root.querySelector(`[data-loan="${name}"]`);
    const result = (name) => root.querySelector(`[data-loan-result="${name}"]`);
    const error = root.querySelector("[data-loan-error]");
    const ratio = Number(root.dataset.incomeRatio) / 100;
    const number = (name) => Number(input(name)?.value);

    const show = (values) => Object.entries(values).forEach(([name, text]) => {
      result(name).textContent = text;
    });

    const incomeText = (payment) => {
      const debt = number("debt") || 0;
      const needed = (payment + debt) / ratio;
      const income = number("income");
      if (!income) return `รายได้ที่ควรมีโดยประมาณ ${baht(needed)} ต่อเดือน`;
      const verdict = income >= needed ? "อยู่ในเกณฑ์ประมาณการ" : "ต่ำกว่าเกณฑ์ประมาณการ";
      return `รายได้ที่ควรมีโดยประมาณ ${baht(needed)} ต่อเดือน รายได้ที่กรอก${verdict}`;
    };

    const apply = () => {
      const values = { price: number("price"), down: number("down"), rate: number("rate"), years: number("years") };
      const valid = isValid(values);
      error.hidden = valid || !input("price").value;
      if (!valid) {
        show({ payment: "-", principal: "-", interest: "-", total: "-" });
        if (result("income")) result("income").textContent = "";
        return;
      }
      const principal = values.price * (1 - values.down / 100);
      const payment = monthlyPayment(principal, values.rate, values.years);
      const total = payment * values.years * 12;
      show({ payment: baht(payment), principal: baht(principal), interest: baht(total - principal), total: baht(total) });
      if (result("income")) result("income").textContent = incomeText(payment);
    };

    root.querySelectorAll("[data-loan]").forEach((field) => field.addEventListener("input", apply));
    apply();
  }

  document.querySelectorAll("[data-loan-calculator]").forEach(init);
})();
