async (page) => {
  await page.goto('http://localhost:8876/monitor?workspace=1');
  await page.getByRole('textbox', { name: 'Mã PIN người đánh giá' }).fill('workspace-verification-only');
  await page.getByRole('button', { name: 'Mở bàn quan sát' }).click();
  await page.getByRole('button', { name: 'Tạo phiên mới' }).click();
  const pairing = await page.locator('.workspacePairing strong').textContent();
  const exam = await page.context().newPage();
  await exam.goto('http://127.0.0.1:8875/exam');
  await exam.getByRole('textbox', { name: 'Mã ghép cặp do người đánh giá cung cấp' }).fill(pairing);
  await exam.getByRole('button', { name: 'Ghép cặp phiên' }).click();
  await exam.getByRole('button', { name: 'Xác nhận đồng ý', exact: true }).click();
  await exam.getByRole('button', { name: 'Hoàn tất kiểm tra trước thi' }).click();
  await page.getByRole('button', { name: 'Kiểm tra trước phiên', exact: true }).click();
  await page.getByRole('button', { name: 'Bắt đầu', exact: true }).click();
  await page.getByRole('heading', { name: 'Đang ghi nhận', exact: true }).waitFor();
  await page.getByRole('figure').screenshot({ path: 'output/completion-2026-09-08/final-skeleton.png' });
  await exam.getByRole('radio', { name: 'Chọn đáp án B' }).click();
  await exam.getByText('Đã lưu', { exact: true }).waitFor();
  await exam.screenshot({ path: 'output/completion-2026-09-08/final-exam.png', fullPage: true });
  await page.bringToFront();
  return { recording: true, answerSaved: true, currentSourceSkeleton: true };
}
