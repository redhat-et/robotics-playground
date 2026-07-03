import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Page } from '@patternfly/react-core';
import RoboticsPlayground from './RoboticsPlayground';

const App: React.FC = () => (
  <BrowserRouter>
    <Page className="pf-v6-theme-dark">
      <Routes>
        <Route path="/*" element={<RoboticsPlayground />} />
      </Routes>
    </Page>
  </BrowserRouter>
);

export default App;
